"""Structured (JSON-lines) logging.

Policy: log *events and counts*, never raw user data. Names, e-mail addresses and
CSV cell values must not be passed to the logger (see tests/security).
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import IO

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    """Render each record as one JSON object per line, including ``extra`` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging(level: str = "INFO", stream: IO[str] | None = None) -> logging.Logger:
    """Configure the ``lab`` logger (idempotent) and return it."""
    logger = logging.getLogger("lab")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
