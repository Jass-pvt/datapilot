"""Ingestion orchestration: fetch -> validate -> store, one transaction per page.

Atomicity model
---------------
Each page is stored in its own transaction together with the run counters and the
failed-record rows. If a later page fails, earlier pages stay committed and the run
is marked ``failed`` with ``pages_completed`` showing how far it got. Re-running the
ingestion is safe because upserts are idempotent.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from lab.books.models import parse_search_payload
from lab.books.repository import upsert_book
from lab.db import transaction
from lab.errors import ApiError, ConfigError, MalformedResponseError

logger = logging.getLogger("lab.books.service")

MAX_PAGES = 10
MAX_LIMIT = 100
MAX_QUERY_LENGTH = 200


class SearchClient(Protocol):
    def search(self, query: str, page: int = 1, limit: int = 20) -> object: ...


@dataclass
class IngestStats:
    run_id: int
    status: str = "running"
    pages_completed: int = 0
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    error: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def validate_params(query: str, pages: int, limit: int) -> str:
    query = " ".join(query.split())
    if not query or len(query) > MAX_QUERY_LENGTH:
        raise ConfigError(f"query must be 1-{MAX_QUERY_LENGTH} characters")
    if not 1 <= pages <= MAX_PAGES:
        raise ConfigError(f"pages must be between 1 and {MAX_PAGES}")
    if not 1 <= limit <= MAX_LIMIT:
        raise ConfigError(f"limit must be between 1 and {MAX_LIMIT}")
    return query


def _finish(conn: sqlite3.Connection, stats: IngestStats, status: str, error: str | None) -> None:
    stats.status, stats.error = status, error
    with transaction(conn):
        conn.execute(
            "UPDATE ingestion_runs SET status = ?, finished_at = ?, error = ? WHERE id = ?",
            (status, _now(), error, stats.run_id),
        )


def ingest_books(
    conn: sqlite3.Connection,
    client: SearchClient,
    query: str,
    *,
    pages: int = 1,
    limit: int = 20,
    source: str = "openlibrary",
) -> IngestStats:
    """Fetch ``pages`` pages for ``query`` and store them. Never raises for API/DB failures."""
    query = validate_params(query, pages, limit)
    with transaction(conn):
        cur = conn.execute(
            "INSERT INTO ingestion_runs (source, query, started_at, status) "
            "VALUES (?, ?, ?, 'running')",
            (source, query, _now()),
        )
        stats = IngestStats(run_id=int(cur.lastrowid or 0))
    logger.info("ingest_started", extra={"run_id": stats.run_id, "pages": pages, "limit": limit})

    for page in range(1, pages + 1):
        try:
            parsed = parse_search_payload(client.search(query, page=page, limit=limit))
        except (ApiError, MalformedResponseError) as exc:
            logger.error("ingest_page_failed", extra={"run_id": stats.run_id, "page": page})
            _finish(conn, stats, "failed", str(exc))
            return stats
        if parsed.docs_total == 0:
            break  # no more results

        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        try:
            with transaction(conn):
                for record in parsed.records:
                    counts[upsert_book(conn, record)] += 1
                for reason, excerpt in parsed.failures:
                    conn.execute(
                        "INSERT INTO failed_records (run_id, reason, raw_excerpt) VALUES (?, ?, ?)",
                        (stats.run_id, reason, excerpt),
                    )
                conn.execute(
                    "UPDATE ingestion_runs SET pages_completed = pages_completed + 1, "
                    "fetched = fetched + ?, inserted = inserted + ?, updated = updated + ?, "
                    "unchanged = unchanged + ?, failed = failed + ? WHERE id = ?",
                    (
                        parsed.docs_total,
                        counts["inserted"],
                        counts["updated"],
                        counts["unchanged"],
                        len(parsed.failures),
                        stats.run_id,
                    ),
                )
        except sqlite3.Error:
            logger.error("ingest_db_error", extra={"run_id": stats.run_id, "page": page})
            _finish(conn, stats, "failed", "a database error occurred; the page was rolled back")
            return stats

        stats.pages_completed += 1
        stats.fetched += parsed.docs_total
        stats.inserted += counts["inserted"]
        stats.updated += counts["updated"]
        stats.unchanged += counts["unchanged"]
        stats.failed += len(parsed.failures)

    _finish(conn, stats, "completed", None)
    logger.info(
        "ingest_completed",
        extra={
            "run_id": stats.run_id,
            "inserted": stats.inserted,
            "updated": stats.updated,
            "unchanged": stats.unchanged,
            "failed": stats.failed,
        },
    )
    return stats
