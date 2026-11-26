import sqlite3

import pytest

from lab.db import connect, init_db, transaction


def test_init_db_is_idempotent_and_keeps_data(conn):
    conn.execute("INSERT INTO users (name, email) VALUES ('A', 'a@x.io')")
    init_db(conn)
    init_db(conn)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_foreign_keys_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO books (api_id, title, author_id) VALUES ('OL1W', 'T', 999)")


def test_unique_api_id_enforced_by_database(conn):
    conn.execute("INSERT INTO books (api_id, title) VALUES ('OL1W', 'T')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO books (api_id, title) VALUES ('OL1W', 'Other')")


def test_check_constraints(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO books (api_id, title, publication_year) VALUES ('OL2W','T',5)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users (name, email) VALUES ('A', 'Upper@X.io')")  # must be lower
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO books (api_id, title) VALUES ('OL3W', NULL)")


def test_cannot_delete_author_with_books(conn):
    conn.execute("INSERT INTO authors (name) VALUES ('X')")
    conn.execute("INSERT INTO books (api_id, title, author_id) VALUES ('OL4W','T',1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM authors WHERE id = 1")


def test_transaction_commits_and_rolls_back(conn):
    with transaction(conn):
        conn.execute("INSERT INTO authors (name) VALUES ('kept')")
    with pytest.raises(RuntimeError), transaction(conn):
        conn.execute("INSERT INTO authors (name) VALUES ('lost')")
        raise RuntimeError("boom")
    names = [r["name"] for r in conn.execute("SELECT name FROM authors")]
    assert names == ["kept"]


def test_newer_schema_version_refused(tmp_path):
    c = connect(tmp_path / "n.db")
    c.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError):
        init_db(c)
