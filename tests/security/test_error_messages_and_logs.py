"""User-visible errors and logs must not leak internals or personal data."""

import re
from pathlib import Path

from lab import cli
from lab.users.importer import import_users

ROOT = Path(__file__).resolve().parents[2]


def run(tmp_path, *args):
    return cli.main(["--db", str(tmp_path / "t.db"), "--log-level", "ERROR", *args])


def test_expected_errors_do_not_leak_paths_sql_or_tracebacks(tmp_path, capsys):
    secret_dir = tmp_path / "very-private-dir"
    code = run(tmp_path, "users", "import", "--csv", str(secret_dir / "x.csv"))
    err = capsys.readouterr().err
    assert code == 1
    for leaked in ("very-private-dir", "Traceback", "sqlite3", "SELECT", ".py"):
        assert leaked not in err


def test_unexpected_exception_is_generic(tmp_path, capsys, monkeypatch, log_stream):
    def explode(*a, **k):
        raise RuntimeError("password=hunter2 /etc/internal/path")

    monkeypatch.setattr(cli, "import_users", explode)
    code = cli.main(["--db", str(tmp_path / "t.db"), "users", "import", "--csv", "x.csv"])
    captured = capsys.readouterr()
    assert code == 2
    assert "hunter2" not in captured.err and "hunter2" not in log_stream.getvalue()
    assert "unexpected internal error" in captured.err


def test_logs_contain_no_names_or_emails(conn, log_stream, tmp_path):
    import_users(conn, ROOT / "data" / "sample_users.csv", rejected_path=tmp_path / "r.csv")
    logs = log_stream.getvalue()
    assert "import_finished" in logs
    for pii in ("alice", "bob@", "example.com", "José", "Robert"):
        assert pii.lower() not in logs.lower()
    assert not re.search(r"[\w.]+@[\w.]+\.\w+", logs)


def test_ingestion_logs_contain_no_record_content(conn, log_stream):
    from lab.books.service import ingest_books
    from tests.conftest import FakeSearchClient

    ingest_books(
        conn, FakeSearchClient({1: {"docs": [{"key": "bad", "title": "SECRET-TITLE"}]}}), "q"
    )
    assert "SECRET-TITLE" not in log_stream.getvalue()
