import math

import pytest

from lab.errors import MalformedResponseError
from lab.scores.chart import create_bar_chart
from lab.scores.models import ScoreRecord, extract_records, validate_records
from lab.scores.stats import compute_stats, rank_students


def recs(*pairs):
    return [ScoreRecord(n, s) for n, s in pairs]


def test_average_median_min_max_std():
    s = compute_stats(recs(("a", 60), ("b", 70), ("c", 80), ("d", 90)))
    assert s.average == 75.0 and s.median == 75.0
    assert (s.minimum, s.maximum, s.count) == (60, 90, 4)
    assert s.std_dev == pytest.approx(math.sqrt(125))


def test_average_single_value():
    assert compute_stats(recs(("a", 42.5))).average == 42.5


def test_empty_dataset_has_no_stats():
    assert compute_stats([]) is None


def test_validation_rules_and_report():
    items = [
        {"name": "A", "score": 90},
        {"name": "a", "score": 10},  # duplicate (case-insensitive)
        {"name": "B", "score": 101},
        {"name": "C", "score": -1},
        {"name": "D"},
        {"name": "E", "score": "80"},
        {"name": "F", "score": True},
        {"name": "G", "score": float("nan")},
        {"name": "  ", "score": 50},
        {"score": 50},
        "junk",
        {"name": "H", "score": 0},
        {"name": "I", "score": 100},
    ]
    valid, report = validate_records(items)
    assert [r.name for r in valid] == ["A", "H", "I"]
    assert (report.total, report.valid, report.invalid, report.duplicates) == (13, 3, 10, 1)


def test_all_invalid_dataset():
    valid, report = validate_records([{"name": "A", "score": 500}])
    assert valid == [] and report.invalid == 1
    assert compute_stats(valid) is None


def test_extract_records_shapes():
    assert extract_records({"students": [1]}) == [1]
    assert extract_records([1, 2]) == [1, 2]
    for bad in ({"students": "x"}, "x", None, {"other": []}):
        with pytest.raises(MalformedResponseError):
            extract_records(bad)


def test_ranking_ties_use_competition_ranking():
    ranked = rank_students(recs(("B", 90), ("A", 90), ("C", 80), ("D", 70)))
    assert [(r, x.name) for r, x in ranked] == [(1, "A"), (1, "B"), (3, "C"), (4, "D")]


def test_chart_created_as_png(tmp_path):
    out = create_bar_chart(recs(("A", 90), ("B", 70)), tmp_path / "sub" / "c.png")
    assert out is not None and out.read_bytes().startswith(b"\x89PNG")


def test_chart_for_empty_data_returns_none(tmp_path):
    assert create_bar_chart([], tmp_path / "c.png") is None
    assert not (tmp_path / "c.png").exists()
