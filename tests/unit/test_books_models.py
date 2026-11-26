import pytest

from lab.books.models import parse_search_payload
from lab.errors import MalformedResponseError
from tests.conftest import doc


def test_valid_doc_is_normalised():
    d = doc(1, title="  Spaced\t Title ", authors=["  Jane   Doe "])
    d["title"] = "  Spaced\t Title "
    result = parse_search_payload({"docs": [d]})
    rec = result.records[0]
    assert (rec.api_id, rec.title, rec.author, rec.publication_year) == (
        "OL1W",
        "Spaced Title",
        "Jane Doe",
        1999,
    )


def test_missing_author_and_year_become_none():
    rec = parse_search_payload({"docs": [doc(2, authors=None, year=None)]}).records[0]
    assert rec.author is None and rec.publication_year is None


def test_first_non_blank_author_is_used():
    rec = parse_search_payload({"docs": [doc(3, authors=["  ", "Real Name"])]}).records[0]
    assert rec.author == "Real Name"


@pytest.mark.parametrize(
    ("bad", "reason_part"),
    [
        ({"title": "No key"}, "key"),
        ({"key": "/works/OL1W"}, "title"),
        ({"key": "/authors/OL1A", "title": "T"}, "work key"),
        ({"key": "/works/OL1W", "title": "   "}, "empty"),
        ({"key": "/works/OL1W", "title": "T", "first_publish_year": 99999}, "year"),
        ({"key": "/works/OL1W", "title": "T", "first_publish_year": "abc"}, "first_publish_year"),
        ({"key": "/works/OL1W", "title": "x" * 501}, "500"),
        ("not an object", "not a JSON object"),
    ],
)
def test_bad_records_become_failures(bad, reason_part):
    result = parse_search_payload({"docs": [bad, doc(9)]})
    assert len(result.records) == 1 and len(result.failures) == 1
    assert reason_part in result.failures[0][0]


@pytest.mark.parametrize("payload", [None, [], "x", {"docs": "no"}, {"nodocs": []}])
def test_malformed_payload_rejected(payload):
    with pytest.raises(MalformedResponseError):
        parse_search_payload(payload)


def test_too_many_docs_rejected():
    with pytest.raises(MalformedResponseError):
        parse_search_payload({"docs": [doc(i) for i in range(501)]})
