import io
import json
import logging

import httpx
import pytest

from lab.books.client import OpenLibraryClient
from lab.db import connect, init_db
from lab.logging_config import setup_logging


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "test.db")
    init_db(connection)
    yield connection
    connection.close()


@pytest.fixture
def log_stream():
    stream = io.StringIO()
    setup_logging("DEBUG", stream)
    yield stream
    logging.getLogger("lab").handlers.clear()


def doc(n: int, title: str = "A Book", authors=("Some Author",), year: int | None = 1999) -> dict:
    d: dict = {"key": f"/works/OL{n}W", "title": f"{title} {n}"}
    if authors is not None:
        d["author_name"] = list(authors)
    if year is not None:
        d["first_publish_year"] = year
    return d


def make_client(handler, **kwargs) -> OpenLibraryClient:
    """Client wired to a mock transport, with instant sleeping."""
    kwargs.setdefault("sleep", lambda _s: None)
    kwargs.setdefault("min_interval", 0.0)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenLibraryClient("https://example.test", http_client=http, **kwargs)


class FakeSearchClient:
    """Returns canned payloads (or raises) per page number."""

    def __init__(self, pages: dict[int, object]):
        self.pages = pages
        self.calls: list[int] = []

    def search(self, query, page=1, limit=20):
        self.calls.append(page)
        value = self.pages.get(page, {"docs": []})
        if isinstance(value, Exception):
            raise value
        return value


def json_response(payload, status=200) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(payload).encode())
