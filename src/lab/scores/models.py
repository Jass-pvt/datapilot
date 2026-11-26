"""Validation of student score records and the data-quality report.

Policies (documented in README):
* ``name`` must be a non-empty string (<= 100 chars after normalisation).
* ``score`` must be a real JSON number in [0, 100]. Numeric *strings* ("85"), booleans,
  NaN/Infinity and missing/null values are rejected, never silently coerced.
* Duplicate students are matched case-insensitively. The FIRST occurrence wins; later
  ones are rejected and reported.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from lab.errors import MalformedResponseError
from lab.text import normalize_text

MIN_SCORE = 0.0
MAX_SCORE = 100.0
MAX_NAME_LENGTH = 100
MAX_RECORDS = 10_000


@dataclass(frozen=True)
class ScoreRecord:
    name: str
    score: float


@dataclass
class QualityReport:
    """Counts and per-record reasons. ``rejected`` holds (record_index, reason)."""

    total: int = 0
    valid: int = 0
    rejected: list[tuple[int, str]] = field(default_factory=list)

    @property
    def invalid(self) -> int:
        return len(self.rejected)

    @property
    def duplicates(self) -> int:
        return sum(1 for _, reason in self.rejected if reason.startswith("duplicate"))


def extract_records(payload: Any) -> list[Any]:
    """Accept ``{"students": [...]}`` or a bare list; reject anything else."""
    items = payload.get("students") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise MalformedResponseError("scores payload must be a list or contain a 'students' list")
    if len(items) > MAX_RECORDS:
        raise MalformedResponseError("scores payload contains too many records")
    return items


def validate_records(items: list[Any]) -> tuple[list[ScoreRecord], QualityReport]:
    report = QualityReport(total=len(items))
    valid: list[ScoreRecord] = []
    first_seen: dict[str, int] = {}

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            report.rejected.append((index, "record is not an object"))
            continue
        raw_name = item.get("name")
        if not isinstance(raw_name, str):
            report.rejected.append((index, "name is missing or not a string"))
            continue
        name = normalize_text(raw_name)
        if not name:
            report.rejected.append((index, "name is empty"))
            continue
        if len(name) > MAX_NAME_LENGTH:
            report.rejected.append((index, "name is too long"))
            continue

        raw_score = item.get("score")
        if raw_score is None:
            report.rejected.append((index, "score is missing"))
            continue
        if isinstance(raw_score, bool) or not isinstance(raw_score, int | float):
            report.rejected.append((index, "score is not a number"))
            continue
        if not math.isfinite(raw_score):
            report.rejected.append((index, "score is not finite"))
            continue
        if not MIN_SCORE <= raw_score <= MAX_SCORE:
            report.rejected.append((index, "score is outside 0-100"))
            continue

        key = name.casefold()
        if key in first_seen:
            report.rejected.append(
                (index, f"duplicate student (first seen at record {first_seen[key]})")
            )
            continue
        first_seen[key] = index
        valid.append(ScoreRecord(name=name, score=float(raw_score)))

    report.valid = len(valid)
    return valid, report
