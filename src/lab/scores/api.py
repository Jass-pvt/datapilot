"""Local FastAPI service that serves the reproducible sample scores.

Controls (all tested): optional API-key authentication (``LAB_API_KEY``), constant-time
key comparison, and a per-client fixed-window rate limit. Bind to 127.0.0.1 (the CLI
default); this is a teaching service, not a hardened production API.
"""

import json
import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request

DEFAULT_DATA = Path("data/sample_scores.json")


def create_app(
    data_path: str | Path = DEFAULT_DATA,
    *,
    api_key: str | None = None,
    rate_limit: int = 60,
    window_seconds: float = 60.0,
    clock: Callable[[], float] = time.monotonic,
) -> FastAPI:
    key = api_key if api_key is not None else os.environ.get("LAB_API_KEY") or None
    data: Any = json.loads(Path(data_path).read_text(encoding="utf-8"))
    windows: dict[str, tuple[float, int]] = {}
    app = FastAPI(title="Lab scores API", docs_url=None, redoc_url=None)

    def guard(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        now = clock()
        start, count = windows.get(client, (now, 0))
        if now - start >= window_seconds:
            start, count = now, 0
        count += 1
        windows[client] = (start, count)
        if count > rate_limit:
            retry = max(1, int(window_seconds - (now - start)))
            raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": str(retry)})
        if key is not None:
            supplied = request.headers.get("X-API-Key", "")
            if not secrets.compare_digest(supplied.encode(), key.encode()):
                raise HTTPException(401, "invalid or missing API key")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/scores", dependencies=[Depends(guard)])
    def scores() -> Any:
        return data

    return app
