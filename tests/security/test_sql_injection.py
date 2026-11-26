"""SQL-injection payloads must be stored/handled as plain data, never executed."""

import pytest

from lab.books.models import BookRecord
from lab.books.repository import list_books, upsert_book
from lab.users.importer import import_users

PAYLOADS = [
    "'); DROP TABLE books;--",
    "' OR '1'='1",
    "Robert'); DROP TABLE users;--",
    '" UNION SELECT name FROM sqlite_master--',
]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_book_fields_are_stored_verbatim_and_tables_survive(conn, payload):
    upsert_book(conn, BookRecord("OL1W", payload, payload, 2000))
    row = list_books(conn)[0]
    assert row["title"] == payload and row["author"] == payload
    # Tables still exist and a parameterised lookup with the payload finds exactly one row.
    found = conn.execute("SELECT COUNT(*) FROM books WHERE title = ?", (payload,)).fetchone()[0]
    assert found == 1
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='users'").fetchone()[0] == 1


@pytest.mark.parametrize("payload", PAYLOADS)
def test_csv_payloads_are_rejected_by_validation_and_never_reach_sql(conn, tmp_path, payload):
    p = tmp_path / "inj.csv"
    p.write_text(f'name,email\n"{payload}",ok@example.com\nFine,"{payload}"\n', encoding="utf-8")
    stats = import_users(conn, p)
    assert stats.inserted == 0 and stats.rejected == 2
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='users'").fetchone()[0] == 1


def test_stacked_statements_are_not_executed(conn):
    import sqlite3

    with pytest.raises((sqlite3.Warning, sqlite3.ProgrammingError)):  # 3.11 / 3.12+
        conn.execute("SELECT 1; DROP TABLE users;")
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='users'").fetchone()[0] == 1
