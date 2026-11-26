import io
import json
import logging

from lab.logging_config import setup_logging


def test_json_lines_with_extra_fields():
    stream = io.StringIO()
    setup_logging("INFO", stream)
    logging.getLogger("lab.test").info("something_happened", extra={"count": 3})
    record = json.loads(stream.getvalue().strip())
    assert record["event"] == "something_happened" and record["count"] == 3
    assert record["level"] == "INFO" and "ts" in record
