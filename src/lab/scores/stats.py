"""Descriptive statistics and ranking.

Why each statistic exists:
* average - the number the assessment asks for.
* median  - robust to outliers; a big gap between mean and median signals skew.
* min/max - the range of the data.
* std_dev - spread. Population std-dev is used because the dataset *is* the whole class.
"""

import statistics
from dataclasses import dataclass

from lab.scores.models import ScoreRecord


@dataclass(frozen=True)
class ScoreStats:
    count: int
    average: float
    median: float
    minimum: float
    maximum: float
    std_dev: float


def compute_stats(records: list[ScoreRecord]) -> ScoreStats | None:
    """Return statistics, or ``None`` for an empty dataset (there is no average of nothing)."""
    if not records:
        return None
    values = [r.score for r in records]
    return ScoreStats(
        count=len(values),
        average=statistics.fmean(values),
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
        std_dev=statistics.pstdev(values),
    )


def rank_students(records: list[ScoreRecord]) -> list[tuple[int, ScoreRecord]]:
    """Standard competition ranking ("1224"): equal scores share a rank, then a gap.

    Order within a tie is alphabetical by name so the output is deterministic.
    """
    ordered = sorted(records, key=lambda r: (-r.score, r.name.casefold()))
    ranked: list[tuple[int, ScoreRecord]] = []
    for position, record in enumerate(ordered, start=1):
        tied = bool(ranked) and ranked[-1][1].score == record.score
        rank = ranked[-1][0] if tied else position
        ranked.append((rank, record))
    return ranked
