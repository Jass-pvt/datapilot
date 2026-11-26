"""Robust CSV -> SQLite user importer.

Duplicate-email policy (exact behaviour)
----------------------------------------
E-mail is normalised (trimmed, lower-cased) and is the identity of a user.
1. Within one file: the FIRST row with an email wins. Every later row with the same
   email is REJECTED (reason names the first row). This is the same in both modes.
2. Against the database, mode ``skip`` (default): a row whose email already exists is
   REJECTED ("email already exists") and the stored row is left untouched.
3. Against the database, mode ``upsert``: the stored row's name is updated if it differs
   (counted ``updated``) or left alone if identical (counted ``unchanged``).
Nothing is silently dropped: every non-inserted row is counted and (optionally) written
to the rejected-rows CSV, except upsert rows that were identical (``unchanged``).
"""

import csv
import io
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from lab.db import transaction
from lab.errors import ConfigError, ImportFailedError, InputError
from lab.text import normalize_text

logger = logging.getLogger("lab.users.importer")

REQUIRED_HEADERS = ("name", "email")
MAX_FILE_BYTES = 5_000_000
MAX_ROWS = 100_000
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254
_NAME_EXTRA_CHARS = set(" '’-.")
_EMAIL_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._%+-]{0,63}@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$"
)
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

Mode = Literal["skip", "upsert"]


@dataclass(frozen=True)
class Rejection:
    row_number: int
    name: str
    email: str
    reason: str


@dataclass
class ImportStats:
    mode: str
    dry_run: bool
    total_rows: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejections: list[Rejection] = field(default_factory=list)

    @property
    def rejected(self) -> int:
        return len(self.rejections)


class RowError(ValueError):
    """A single row failed validation; the message is a safe, fixed reason."""


def validate_name(raw: str) -> str:
    name = normalize_text(raw)
    if not name:
        raise RowError("name is empty")
    if len(name) > MAX_NAME_LENGTH:
        raise RowError("name is longer than 100 characters")
    if not any(ch.isalpha() for ch in name):
        raise RowError("name must contain a letter")
    if any(not (ch.isalpha() or ch in _NAME_EXTRA_CHARS) for ch in name):
        raise RowError("name contains disallowed characters")
    return name


def validate_email(raw: str) -> str:
    email = raw.strip().lower()
    if not email:
        raise RowError("email is empty")
    if len(email) > MAX_EMAIL_LENGTH:
        raise RowError("email is longer than 254 characters")
    if ".." in email or not _EMAIL_PATTERN.match(email):
        raise RowError("email format is invalid")
    return email


def _read_rows(path: Path, max_bytes: int, max_rows: int) -> list[tuple[int, list[str]]]:
    """Return ``(line_number, cells)`` for each data row, after file-level checks."""
    if not path.is_file():
        raise InputError("the CSV file does not exist")
    size = path.stat().st_size
    if size == 0:
        raise InputError("the CSV file is empty")
    if size > max_bytes:
        raise InputError("the CSV file is too large")
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InputError("the CSV file is not valid UTF-8") from None
    if not text.strip():
        raise InputError("the CSV file is empty")

    reader = csv.reader(io.StringIO(text, newline=""))
    rows: list[tuple[int, list[str]]] = []
    try:
        header = next(reader)
        headers = [normalize_text(h).casefold() for h in header]
        if len(set(headers)) != len(headers):
            raise InputError("the CSV header contains duplicate columns")
        missing = [h for h in REQUIRED_HEADERS if h not in headers]
        if missing:
            raise InputError(f"the CSV header is missing required column(s): {', '.join(missing)}")
        if headers != list(REQUIRED_HEADERS):
            raise InputError("the CSV header must be exactly: name,email")
        for cells in reader:
            rows.append((reader.line_num, cells))
            if len(rows) > max_rows:
                raise InputError("the CSV file has too many rows")
    except csv.Error:
        raise InputError("the CSV file is malformed") from None
    return rows


def _csv_safe(value: str) -> str:
    """Neutralise spreadsheet formula injection in cells we write back out."""
    return "'" + value if value.startswith(_FORMULA_PREFIXES) else value


def write_rejections(path: str | Path, rejections: list[Rejection]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row_number", "name", "email", "reason"])
        for item in rejections:
            writer.writerow(
                [item.row_number, _csv_safe(item.name), _csv_safe(item.email), item.reason]
            )


class _DryRunRollback(Exception):  # noqa: N818 - control-flow signal, not an error
    pass


def import_users(
    conn: sqlite3.Connection,
    csv_path: str | Path,
    *,
    mode: Mode = "skip",
    dry_run: bool = False,
    rejected_path: str | Path | None = None,
    max_bytes: int = MAX_FILE_BYTES,
    max_rows: int = MAX_ROWS,
) -> ImportStats:
    """Import users. All database work happens in ONE transaction (all-or-nothing)."""
    if mode not in ("skip", "upsert"):
        raise ConfigError("mode must be 'skip' or 'upsert'")
    rows = _read_rows(Path(csv_path), max_bytes, max_rows)
    stats = ImportStats(mode=mode, dry_run=dry_run, total_rows=len(rows))

    candidates: list[tuple[int, str, str]] = []
    first_row_for_email: dict[str, int] = {}
    for line_no, cells in rows:
        if not any(cell.strip() for cell in cells):
            stats.rejections.append(Rejection(line_no, "", "", "row is empty"))
            continue
        if len(cells) != len(REQUIRED_HEADERS):
            stats.rejections.append(
                Rejection(line_no, "", "", f"expected 2 columns, found {len(cells)}")
            )
            continue
        raw_name, raw_email = cells
        try:
            name = validate_name(raw_name)
            email = validate_email(raw_email)
        except RowError as exc:
            stats.rejections.append(Rejection(line_no, raw_name, raw_email, str(exc)))
            continue
        if email in first_row_for_email:
            reason = f"duplicate email in file (first seen at row {first_row_for_email[email]})"
            stats.rejections.append(Rejection(line_no, name, email, reason))
            continue
        first_row_for_email[email] = line_no
        candidates.append((line_no, name, email))

    try:
        with transaction(conn):
            for line_no, name, email in candidates:
                existing = conn.execute(
                    "SELECT id, name FROM users WHERE email = ?", (email,)
                ).fetchone()
                if existing is None:
                    conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
                    stats.inserted += 1
                elif mode == "upsert":
                    if existing["name"] == name:
                        stats.unchanged += 1
                    else:
                        conn.execute(
                            "UPDATE users SET name = ?, "
                            "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
                            (name, existing["id"]),
                        )
                        stats.updated += 1
                else:
                    stats.rejections.append(
                        Rejection(line_no, name, email, "email already exists in database")
                    )
            if dry_run:
                raise _DryRunRollback
    except _DryRunRollback:
        pass
    except sqlite3.Error:
        logger.error("import_db_error", extra={"rows": len(rows)})
        raise ImportFailedError("a database error occurred; no changes were saved") from None

    stats.rejections.sort(key=lambda r: r.row_number)
    if rejected_path is not None:
        write_rejections(rejected_path, stats.rejections)
    logger.info(
        "import_finished",
        extra={
            "mode": mode,
            "dry_run": dry_run,
            "rows": stats.total_rows,
            "inserted": stats.inserted,
            "updated": stats.updated,
            "unchanged": stats.unchanged,
            "rejected": stats.rejected,
        },
    )
    return stats


def list_users(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name, email FROM users ORDER BY id LIMIT ?", (limit,)
    ).fetchall()
