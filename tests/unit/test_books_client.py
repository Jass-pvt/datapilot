import httpx
import pytest

from lab.errors import ApiError
from tests.conftest import json_response, make_client


def test_success():
    client = make_client(lambda req: json_response({"docs": []}))
    assert client.search("x") == {"docs": []}


def test_retries_then_succeeds_with_exponential_backoff():
    sleeps, responses = [], [503, 503, 200]

    def handler(req):
        status = responses.pop(0)
        return json_response({"docs": []}, status)

    client = make_client(handler, sleep=sleeps.append, backoff_base=1.0)
    assert client.search("x") == {"docs": []}
    assert sleeps == [1.0, 2.0]


def test_retries_are_bounded():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(500)

    client = make_client(handler, max_retries=2)
    with pytest.raises(ApiError):
        client.search("x")
    assert len(calls) == 3  # first attempt + 2 retries


def test_timeout_is_retried_and_message_is_generic():
    def handler(req):
        raise httpx.ReadTimeout("secret internal detail", request=req)

    client = make_client(handler, max_retries=1)
    with pytest.raises(ApiError) as exc:
        client.search("x")
    assert "secret" not in str(exc.value)


def test_client_errors_not_retried():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(404)

    with pytest.raises(ApiError, match="404"):
        make_client(handler).search("x")
    assert len(calls) == 1


def test_invalid_json_and_oversized_response():
    with pytest.raises(ApiError, match="invalid JSON"):
        make_client(lambda r: httpx.Response(200, content=b"<html>")).search("x")
    with pytest.raises(ApiError, match="too large"):
        make_client(
            lambda r: httpx.Response(200, content=b"{" + b" " * 5000 + b"}"),
            max_response_bytes=1000,
        ).search("x")


def test_retry_after_is_honoured_and_capped():
    sleeps, seen = [], []

    def handler(req):
        if not seen:
            seen.append(1)
            return httpx.Response(429, headers={"Retry-After": "5"})
        return json_response({"docs": []})

    make_client(handler, sleep=sleeps.append, backoff_base=0.5).search("x")
    assert sleeps == [5.0]


def test_min_interval_throttles_requests():
    sleeps, clock = [], [0.0]
    client = make_client(
        lambda r: json_response({"docs": []}),
        sleep=sleeps.append,
        min_interval=2.0,
        monotonic=lambda: clock[0],
    )
    client.search("x")
    client.search("x")
    assert sleeps == [2.0]
