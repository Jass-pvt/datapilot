"""SQLite connection, schema and transaction helpers.

Design notes
------------
* ``isolation_level=None`` puts the sqlite3 module in autocommit mode so *we*
  control transaction boundaries explicitly (``BEGIN IMMEDIATE`` ... ``COMMIT``).
* ``PRAGMA foreign_keys = ON`` is per-connection in SQLite and off by default.
* Integrity rules live in the schema (NOT NULL / UNIQUE / CHECK / FOREIGN KEY),
  so they hold even if application code has a bug.
* ``books.id`` is *our* surrogate key. ``books.api_id`` is the identifier assigned
  by Open Library. We keep both: the API id is the natural key used to detect
  duplicates (UNIQUE), while the integer id is a small, stable key we control
  (foreign keys, joins) and that does not break if the API changes its format.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

_NOW = "strftime('%Y-%m-%dT%H:%M:%SZ','now')"

SCHEMA = f"""
BEGIN;

CREATE TABLE IF NOT EXISTS authors (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (length(name) BETWEEN 1 AND 200)
);

CREATE TABLE IF NOT EXISTS books (
    id               INTEGER PRIMARY KEY,
    api_id           TEXT    NOT NULL UNIQUE CHECK (length(api_id) BETWEEN 1 AND 64),
    title            TEXT    NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
    author_id        INTEGER REFERENCES authors(id) ON DELETE RESTRICT,
    publication_year INTEGER CHECK (publication_year IS NULL
                                    OR publication_year BETWEEN 1000 AND 2100),
    created_at       TEXT NOT NULL DEFAULT ({_NOW}),
    updated_at       TEXT NOT NULL DEFAULT ({_NOW})
);
CREATE INDEX IF NOT EXISTS idx_books_author_id ON books(author_id);
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id              INTEGER PRIMARY KEY,
    source          TEXT NOT NULL,
    query           TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL CHECK (status IN ('running','completed','failed')),
    pages_completed INTEGER NOT NULL DEFAULT 0,
    fetched         INTEGER NOT NULL DEFAULT 0,
    inserted        INTEGER NOT NULL DEFAULT 0,
    updated         INTEGER NOT NULL DEFAULT 0,
    unchanged       INTEGER NOT NULL DEFAULT 0,
    failed          INTEGER NOT NULL DEFAULT 0,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS failed_records (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES ingestion_runs(id) ON DELETE CASCADE,
    reason      TEXT NOT NULL,
    raw_excerpt TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_failed_records_run ON failed_records(run_id);

CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    email      TEXT NOT NULL UNIQUE
               CHECK (length(email) BETWEEN 3 AND 254 AND email = lower(email)),
    created_at TEXT NOT NULL DEFAULT ({_NOW}),
    updated_at TEXT NOT NULL DEFAULT ({_NOW})
);

PRAGMA user_version = {SCHEMA_VERSION};
COMMIT;
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with foreign keys enforced and dict-like rows."""
    path = str(db_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the schema if missing. Safe to call repeatedly; never drops data.

    Refuses to run against a database created by a *newer* schema version.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        msg = f"database schema version {current} is newer than supported {SCHEMA_VERSION}"
        raise RuntimeError(msg)
    conn.executescript(SCHEMA)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block atomically: COMMIT on success, ROLLBACK on *any* exception.

    ``BEGIN IMMEDIATE`` takes the write lock up front so a concurrent writer
    fails fast instead of failing half-way through the block.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
