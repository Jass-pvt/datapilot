"""Transactions roll back after failures; interrupted runs leave consistent data."""

import pytest

from lab.books import service
from lab.books.service import ingest_books
from lab.errors import ImportFailedError
from tests.conftest import FakeSearchClient, doc


def test_user_import_rolls_back_entirely_on_database_failure(conn, tmp_path):
    conn.execute(
        "CREATE TRIGGER boom BEFORE INSERT ON users WHEN NEW.email = 'boom@x.io' "
        "BEGIN SELECT RAISE(ABORT, 'simulated failure'); END"
    )
    p = tmp_path / "u.csv"
    p.write_text("name,email\nAda,ada@x.io\nBob,bob@x.io\nBoom,boom@x.io\nCy,cy@x.io\n")
    with pytest.raises(ImportFailedError) as exc:
        import_users_(conn, p)
    assert "simulated" not in str(exc.value)  # internal detail not leaked
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def import_users_(conn, path):
    from lab.users.importer import import_users

    return import_users(conn, path)


def test_book_page_rolls_back_on_database_failure(conn):
    conn.execute(
        "CREATE TRIGGER boom BEFORE INSERT ON books WHEN NEW.title LIKE '%BOOM%' "
        "BEGIN SELECT RAISE(ABORT, 'simulated failure'); END"
    )
    docs = [doc(1), {"key": "/works/OL2W", "title": "BOOM"}, doc(3)]
    stats = ingest_books(conn, FakeSearchClient({1: {"docs": docs}}), "q")
    assert stats.status == "failed" and "simulated" not in (stats.error or "")
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0
    run = conn.execute("SELECT status, pages_completed, fetched FROM ingestion_runs").fetchone()
    assert (run["status"], run["pages_completed"], run["fetched"]) == ("failed", 0, 0)


def test_interrupt_mid_page_rolls_back_that_page(conn, monkeypatch):
    calls = {"n": 0}
    real = service.upsert_book

    def flaky(c, record):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt
        return real(c, record)

    monkeypatch.setattr(service, "upsert_book", flaky)
    with pytest.raises(KeyboardInterrupt):
        ingest_books(conn, FakeSearchClient({1: {"docs": [doc(1), doc(2)]}}), "q")
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0
    # The connection is usable again (no dangling transaction) and run is visibly unfinished.
    assert conn.execute("SELECT status FROM ingestion_runs").fetchone()["status"] == "running"
    monkeypatch.undo()
    stats = ingest_books(conn, FakeSearchClient({1: {"docs": [doc(1), doc(2)]}}), "q")
    assert stats.inserted == 2


def test_interrupt_between_pages_keeps_committed_pages_and_rerun_converges(conn):
    class Interrupting(FakeSearchClient):
        def search(self, query, page=1, limit=20):
            if page == 2:
                raise KeyboardInterrupt
            return super().search(query, page, limit)

    pages = {1: {"docs": [doc(1)]}, 2: {"docs": [doc(2)]}}
    with pytest.raises(KeyboardInterrupt):
        ingest_books(conn, Interrupting(pages), "q", pages=2)
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1
    ingest_books(conn, FakeSearchClient(pages), "q", pages=2)
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 2


def test_repeated_ingestion_never_creates_duplicates(conn):
    payload = {1: {"docs": [doc(i) for i in range(1, 6)]}}
    for _ in range(5):
        ingest_books(conn, FakeSearchClient(payload), "q")
    assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 5
    dupes = conn.execute("SELECT api_id FROM books GROUP BY api_id HAVING COUNT(*) > 1").fetchall()
    assert dupes == []


def test_referential_integrity_after_ingest(conn):
    ingest_books(conn, FakeSearchClient({1: {"docs": [doc(1), doc(2, authors=None)]}}), "q")
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
