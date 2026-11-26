"""Load score data from a local JSON file or an HTTP(S) endpoint, with size limits."""

import json
from pathlib import Path
from typing import Any

import httpx

from lab.errors import ApiError, InputError

MAX_BYTES = 1_000_000


def load_scores(
    source: str, *, http_client: httpx.Client | None = None, timeout: float = 10.0
) -> Any:
    """Return decoded JSON from ``source`` (path or http/https URL)."""
    if source.lower().startswith(("http://", "https://")):
        return _load_url(source, http_client, timeout)
    return _load_file(Path(source))


def _load_file(path: Path) -> Any:
    if not path.is_file():
        raise InputError("the scores file does not exist")
    if path.stat().st_size > MAX_BYTES:
        raise InputError("the scores file is too large")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise InputError("the scores file is not valid UTF-8 JSON") from None


def _load_url(url: str, http_client: httpx.Client | None, timeout: float) -> Any:
    client = http_client or httpx.Client(timeout=timeout)
    try:
        with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise ApiError(f"the scores API returned HTTP status {response.status_code}")
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ApiError("the scores API response was too large")
    except httpx.HTTPError:
        raise ApiError("the scores API could not be reached") from None
    finally:
        if http_client is None:
            client.close()
    try:
        return json.loads(bytes(body))
    except ValueError:
        raise ApiError("the scores API returned invalid JSON") from None
