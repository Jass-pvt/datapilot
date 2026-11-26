"""Authentication and rate limiting of the local scores API."""

from pathlib import Path

from fastapi.testclient import TestClient

from lab.scores.api import create_app

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_scores.json"


def test_api_key_required_when_configured():
    c = TestClient(create_app(SAMPLE, api_key="s3cret"))
    assert c.get("/scores").status_code == 401
    assert c.get("/scores", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.get("/scores", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert c.get("/health").status_code == 200  # health stays open


def test_rate_limit_returns_429_then_recovers():
    now = [0.0]
    c = TestClient(create_app(SAMPLE, rate_limit=3, window_seconds=10, clock=lambda: now[0]))
    assert [c.get("/scores").status_code for _ in range(4)] == [200, 200, 200, 429]
    assert "retry-after" in {k.lower() for k in c.get("/scores").headers}
    now[0] = 11.0
    assert c.get("/scores").status_code == 200


def test_error_body_has_no_internals():
    c = TestClient(create_app(SAMPLE, api_key="k"))
    response = c.get("/scores")
    assert response.json() == {"detail": "invalid or missing API key"}
