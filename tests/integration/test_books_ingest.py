import pytest

from lab.books.repository import database_stats, list_books
from lab.books.service import ingest_books
from lab.errors import ApiError, ConfigError
from tests.conftest import FakeSearchClient, doc


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_ingest_stores_books_and_stats(conn):
    client = FakeSearchClient({1: {"docs": [doc(1), doc(2, authors=None), doc(3, year=None)]}})
    stats = ingest_books(conn, client, "python", pages=1)
    assert (stats.status, stats.fetched, stats.inserted, stats.failed) == ("completed", 3, 3, 0)
    rows = {r["api_id"]: r for r in list_books(conn)}
    assert rows["OL2W"]["author"] is None and rows["OL3W"]["publication_year"] is None


def test_repeated_ingestion_is_idempotent(conn):
    payload = {1: {"docs": [doc(1), doc(2)]}}
    first = ingest_books(conn, FakeSearchClient(payload), "q")
    second = ingest_books(conn, FakeSearchClient(payload), "q")
    third = ingest_books(conn, FakeSearchClient(payload), "q")
    assert (first.inserted, second.inserted, third.inserted) == (2, 0, 0)
    assert second.unchanged == 2
    assert count(conn, "books") == 2 and count(conn, "authors") == 1


def test_changed_upstream_data_is_updated_not_duplicated(conn):
    ingest_books(conn, FakeSearchClient({1: {"docs": [doc(1, year=1990)]}}), "q")
    stats = ingest_books(conn, FakeSearchClient({1: {"docs": [doc(1, year=1991)]}}), "q")
    assert stats.updated == 1 and count(conn, "books") == 1
    assert list_books(conn)[0]["publication_year"] == 1991


def test_duplicate_inside_one_response_does_not_duplicate(conn):
    stats = ingest_books(conn, FakeSearchClient({1: {"docs": [doc(1), doc(1)]}}), "q")
    assert stats.inserted == 1 and stats.unchanged == 1 and count(conn, "books") == 1


def test_invalid_records_are_reported_not_stored(conn):
    payload = {1: {"docs": [doc(1), {"key": "bad", "title": "T"}, {"title": "no key"}]}}
    stats = ingest_books(conn, FakeSearchClient(payload), "q")
    assert (stats.inserted, stats.failed) == (1, 2)
    reasons = [r["reason"] for r in conn.execute("SELECT reason FROM failed_records")]
    assert len(reasons) == 2


def test_pagination_stops_on_empty_page(conn):
    client = FakeSearchClient({1: {"docs": [doc(1)]}, 2: {"docs": []}, 3: {"docs": [doc(3)]}})
    stats = ingest_books(conn, client, "q", pages=3)
    assert client.calls == [1, 2] and stats.pages_completed == 1


def test_api_failure_on_page_two_keeps_page_one(conn):
    client = FakeSearchClient({1: {"docs": [doc(1)]}, 2: ApiError("the API could not be reached")})
    stats = ingest_books(conn, client, "q", pages=2)
    assert stats.status == "failed" and stats.pages_completed == 1
    assert count(conn, "books") == 1
    run = conn.execute("SELECT status, pages_completed FROM ingestion_runs").fetchone()
    assert (run["status"], run["pages_completed"]) == ("failed", 1)


@pytest.mark.parametrize(
    ("query", "pages", "limit"),
    [("", 1, 10), ("x", 0, 10), ("x", 11, 10), ("x", 1, 0), ("x", 1, 101)],
)
def test_parameter_validation(conn, query, pages, limit):
    with pytest.raises(ConfigError):
        ingest_books(conn, FakeSearchClient({}), query, pages=pages, limit=limit)


def test_database_stats(conn):
    ingest_books(conn, FakeSearchClient({1: {"docs": [doc(1), doc(2, authors=None)]}}), "q")
    stats = database_stats(conn)
    assert stats["books"] == 2 and stats["books_without_author"] == 1
    assert stats["recent_runs"][0]["status"] == "completed"
