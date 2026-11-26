import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lab.errors import ApiError, InputError
from lab.scores.api import create_app
from lab.scores.client import load_scores
from lab.scores.models import extract_records, validate_records
from lab.scores.stats import compute_stats

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_scores.json"


def test_sample_dataset_quality_and_average():
    valid, report = validate_records(extract_records(load_scores(str(SAMPLE))))
    assert (report.total, report.valid, report.invalid, report.duplicates) == (13, 8, 5, 1)
    assert compute_stats(valid).average == pytest.approx(81.9375)


def test_api_serves_sample_and_client_consumes_it():
    http = TestClient(create_app(SAMPLE))
    assert http.get("/health").json() == {"status": "ok"}
    payload = load_scores("http://testserver/scores", http_client=http)
    assert len(payload["students"]) == 13


def test_client_error_paths(tmp_path):
    with pytest.raises(InputError):
        load_scores(str(tmp_path / "missing.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(InputError):
        load_scores(str(bad))
    http = TestClient(create_app(SAMPLE, api_key="k"))
    with pytest.raises(ApiError, match="401"):
        load_scores("http://testserver/scores", http_client=http)


def test_create_app_from_custom_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"students": []}))
    assert TestClient(create_app(p)).get("/scores").json() == {"students": []}
