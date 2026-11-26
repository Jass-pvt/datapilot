"""Validation and normalisation of Open Library search results.

Per-record problems produce a *failure* (stored and reported). Problems with the
overall response shape raise ``MalformedResponseError`` and abort that page.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from lab.errors import MalformedResponseError
from lab.text import normalize_text

MAX_DOCS_PER_PAGE = 500
MIN_YEAR = 1000
_KEY_PATTERN = re.compile(r"^/works/(OL\d{1,18}W)$")


class OpenLibraryDoc(BaseModel):
    """Shape we expect for one ``docs`` entry. Unknown fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    key: str
    title: str
    author_name: list[str] | None = None
    first_publish_year: int | None = None


@dataclass(frozen=True)
class BookRecord:
    """A validated, normalised book ready for storage."""

    api_id: str
    title: str
    author: str | None
    publication_year: int | None


@dataclass
class ParseResult:
    records: list[BookRecord] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)  # (reason, excerpt)
    docs_total: int = 0


def _excerpt(doc: Any) -> str:
    try:
        return json.dumps(doc, default=str, ensure_ascii=False)[:200]
    except (TypeError, ValueError):
        return "<unserialisable>"


def _to_record(raw: OpenLibraryDoc) -> BookRecord:
    """Normalise a schema-valid doc. Raises ``ValueError`` with a safe reason."""
    match = _KEY_PATTERN.match(raw.key.strip())
    if not match:
        raise ValueError("unrecognised work key format")

    title = normalize_text(raw.title)
    if not title:
        raise ValueError("title is empty after normalisation")
    if len(title) > 500:
        raise ValueError("title longer than 500 characters")

    author: str | None = None
    for candidate in raw.author_name or []:
        cleaned = normalize_text(candidate)
        if cleaned:
            author = cleaned
            break
    if author is not None and len(author) > 200:
        raise ValueError("author name longer than 200 characters")

    year = raw.first_publish_year
    if year is not None and not (MIN_YEAR <= year <= date.today().year + 1):
        raise ValueError("publication year out of range")

    return BookRecord(api_id=match.group(1), title=title, author=author, publication_year=year)


def parse_search_payload(payload: Any) -> ParseResult:
    """Validate one search response and split it into records and failures."""
    if not isinstance(payload, dict) or not isinstance(payload.get("docs"), list):
        raise MalformedResponseError("API response is missing a 'docs' list")
    docs = payload["docs"]
    if len(docs) > MAX_DOCS_PER_PAGE:
        raise MalformedResponseError("API response contains too many records")

    result = ParseResult(docs_total=len(docs))
    for doc in docs:
        if not isinstance(doc, dict):
            result.failures.append(("record is not a JSON object", _excerpt(doc)))
            continue
        try:
            raw = OpenLibraryDoc.model_validate(doc)
            result.records.append(_to_record(raw))
        except ValidationError as exc:
            # Report field names only: never echo the offending values.
            fields = sorted({str(err["loc"][0]) for err in exc.errors() if err["loc"]})
            result.failures.append(
                (f"schema validation failed for: {', '.join(fields)}", _excerpt(doc))
            )
        except ValueError as exc:
            result.failures.append((str(exc), _excerpt(doc)))
    return result
