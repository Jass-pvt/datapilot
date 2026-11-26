"""HTTP client for Open Library with timeouts, bounded retries and rate limiting."""

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from lab.errors import ApiError

logger = logging.getLogger("lab.books.client")

DEFAULT_BASE_URL = "https://openlibrary.org"
USER_AGENT = "secure-data-ai-lab/0.1 (assessment project)"
MAX_RETRY_AFTER = 30.0


class _Retryable(Exception):
    def __init__(self, reason: str, retry_after: float | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


class OpenLibraryClient:
    """Fetch search pages.

    * ``timeout``: every request has one (httpx has no default total timeout).
    * ``max_retries``: *bounded*; retries only network errors, 429 and 5xx.
    * back-off: ``backoff_base * 2**attempt`` seconds, capped; honours ``Retry-After``.
    * ``min_interval``: minimum seconds between requests (client-side rate limit).
    * ``max_response_bytes``: the body is read in chunks and aborted past this size.
    ``sleep`` and ``monotonic`` are injectable so tests run instantly.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        http_client: httpx.Client | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        backoff_cap: float = 8.0,
        min_interval: float = 0.5,
        max_response_bytes: int = 2_000_000,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http_client or httpx.Client(
            timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=False
        )
        self._owns_http = http_client is None
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.min_interval = min_interval
        self.max_response_bytes = max_response_bytes
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request: float | None = None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "OpenLibraryClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval - (self._monotonic() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._monotonic()

    def search(self, query: str, page: int = 1, limit: int = 20) -> Any:
        """Return the decoded JSON for one search page (structure NOT yet validated)."""
        params: dict[str, str | int] = {
            "q": query,
            "page": page,
            "limit": limit,
            "fields": "key,title,author_name,first_publish_year",
        }
        attempt = 0
        while True:
            self._throttle()
            try:
                return self._get_json(f"{self.base_url}/search.json", params)
            except _Retryable as exc:
                if attempt >= self.max_retries:
                    logger.error(
                        "api_gave_up", extra={"attempts": attempt + 1, "reason": exc.reason}
                    )
                    raise ApiError("the API could not be reached after several attempts") from None
                delay = min(self.backoff_cap, self.backoff_base * (2**attempt))
                if exc.retry_after is not None:
                    delay = min(max(delay, exc.retry_after), MAX_RETRY_AFTER)
                logger.warning(
                    "api_retry",
                    extra={"attempt": attempt + 1, "delay_s": delay, "reason": exc.reason},
                )
                self._sleep(delay)
                attempt += 1

    def _get_json(self, url: str, params: dict[str, str | int]) -> Any:
        try:
            with self._http.stream("GET", url, params=params) as response:
                status = response.status_code
                if status == 429 or 500 <= status <= 599:
                    raise _Retryable(f"http_{status}", _parse_retry_after(response))
                if status != 200:
                    raise ApiError(f"the API returned HTTP status {status}")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > self.max_response_bytes:
                        raise ApiError("the API response was too large")
        except httpx.TimeoutException:
            raise _Retryable("timeout") from None
        except httpx.TransportError:
            raise _Retryable("network_error") from None
        try:
            return json.loads(bytes(body))
        except ValueError:
            raise ApiError("the API returned invalid JSON") from None


def _parse_retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
