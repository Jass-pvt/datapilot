"""All SQL for books. Every statement is parameterised (no string building)."""

import sqlite3
from typing import Literal

from lab.books.models import BookRecord

UpsertOutcome = Literal["inserted", "updated", "unchanged"]


def get_or_create_author(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO authors (name) VALUES (?)", (name,))
    row = conn.execute("SELECT id FROM authors WHERE name = ?", (name,)).fetchone()
    return int(row["id"])


def upsert_book(conn: sqlite3.Connection, record: BookRecord) -> UpsertOutcome:
    """Insert, update or leave a book untouched, keyed on the API id.

    Idempotent: running it twice with the same record changes nothing the second
    time. The UNIQUE constraint on ``books.api_id`` is the final safeguard even if
    this function's read-then-write logic were bypassed.
    """
    author_id = get_or_create_author(conn, record.author) if record.author else None
    existing = conn.execute(
        "SELECT id, title, author_id, publication_year FROM books WHERE api_id = ?",
        (record.api_id,),
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO books (api_id, title, author_id, publication_year) VALUES (?, ?, ?, ?)",
            (record.api_id, record.title, author_id, record.publication_year),
        )
        return "inserted"
    unchanged = (
        existing["title"] == record.title
        and existing["author_id"] == author_id
        and existing["publication_year"] == record.publication_year
    )
    if unchanged:
        return "unchanged"
    conn.execute(
        "UPDATE books SET title = ?, author_id = ?, publication_year = ?, "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
        (record.title, author_id, record.publication_year, existing["id"]),
    )
    return "updated"


def list_books(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT b.id, b.api_id, b.title, a.name AS author, b.publication_year "
        "FROM books b LEFT JOIN authors a ON a.id = b.author_id "
        "ORDER BY b.title COLLATE NOCASE, b.id LIMIT ?",
        (limit,),
    ).fetchall()


def database_stats(conn: sqlite3.Connection) -> dict[str, object]:
    """Aggregate figures about stored books and recent ingestion runs."""
    totals = conn.execute(
        "SELECT COUNT(*) AS books, "
        "SUM(author_id IS NULL) AS unknown_author, "
        "SUM(publication_year IS NULL) AS unknown_year "
        "FROM books"
    ).fetchone()
    authors = conn.execute("SELECT COUNT(*) FROM authors").fetchone()[0]
    runs = conn.execute(
        "SELECT id, status, pages_completed, fetched, inserted, updated, unchanged, failed "
        "FROM ingestion_runs ORDER BY id DESC LIMIT 5"
    ).fetchall()
    return {
        "books": totals["books"],
        "authors": authors,
        "books_without_author": totals["unknown_author"] or 0,
        "books_without_year": totals["unknown_year"] or 0,
        "recent_runs": [dict(r) for r in runs],
    }
