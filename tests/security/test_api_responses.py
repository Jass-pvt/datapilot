"""Malformed external API responses must never corrupt the database."""

import httpx

from lab.books.service import ingest_books
from tests.conftest import FakeSearchClient, doc, make_client


def books(conn):
    return conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]


def test_wrong_shape_page_stores_nothing(conn):
    for bad in (None, [], "x", {"docs": "nope"}, {"unexpected": 1}):
        stats = ingest_books(conn, FakeSearchClient({1: bad}), "q")
        assert stats.status == "failed"
    assert books(conn) == 0


def test_malformed_page_two_keeps_good_page_one(conn):
    stats = ingest_books(
        conn, FakeSearchClient({1: {"docs": [doc(1)]}, 2: {"docs": "broken"}}), "q", pages=2
    )
    assert stats.status == "failed" and books(conn) == 1


def test_hostile_field_values_are_rejected_not_stored(conn):
    docs = [
        {"key": "/works/OL1W", "title": {"nested": "object"}},
        {"key": "/works/OL2W", "title": "T", "author_name": "not-a-list"},
        {"key": "/works/OL3W", "title": "T", "first_publish_year": 1e9},
        {"key": "/works/OL4W", "title": "x" * 100_000},
        {"key": ["list"], "title": "T"},
        doc(5),
    ]
    stats = ingest_books(conn, FakeSearchClient({1: {"docs": docs}}), "q")
    assert (stats.inserted, stats.failed) == (1, 5)
    excerpt_lengths = [len(r[0]) for r in conn.execute("SELECT raw_excerpt FROM failed_records")]
    assert max(excerpt_lengths) <= 200  # stored excerpts are bounded


def test_invalid_json_through_real_client_is_reported(conn):
    client = make_client(lambda r: httpx.Response(200, content=b"<html>oops</html>"))
    stats = ingest_books(conn, client, "q")
    assert stats.status == "failed" and "invalid JSON" in stats.error
    assert books(conn) == 0


def test_persistent_server_errors_fail_cleanly(conn):
    client = make_client(lambda r: httpx.Response(503), max_retries=2)
    stats = ingest_books(conn, client, "q")
    assert stats.status == "failed" and books(conn) == 0
