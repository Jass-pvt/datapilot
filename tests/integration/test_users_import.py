import csv
from pathlib import Path

import pytest

from lab.errors import ConfigError, InputError
from lab.users.importer import import_users, list_users

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_users.csv"


def write(tmp_path, text, name="u.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_sample_csv_import(conn, tmp_path):
    rejected = tmp_path / "rej.csv"
    stats = import_users(conn, SAMPLE, rejected_path=rejected)
    assert (stats.total_rows, stats.inserted, stats.rejected) == (11, 6, 5)
    emails = {r["email"] for r in list_users(conn)}
    assert "bob@example.com" in emails and "alice@example.com" in emails
    rows = list(csv.DictReader(rejected.open(encoding="utf-8")))
    assert [r["row_number"] for r in rows] == ["5", "7", "8", "9", "10"]
    assert any("duplicate email in file" in r["reason"] for r in rows)


def test_whitespace_is_normalised(conn):
    import_users(conn, SAMPLE)
    row = conn.execute("SELECT name FROM users WHERE email='bob@example.com'").fetchone()
    assert row["name"] == "Bob Smith"


def test_dry_run_changes_nothing_but_reports_same_numbers(conn):
    dry = import_users(conn, SAMPLE, dry_run=True)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    real = import_users(conn, SAMPLE)
    assert (dry.inserted, dry.rejected) == (real.inserted, real.rejected)


def test_skip_mode_rejects_existing_email_and_keeps_original(conn, tmp_path):
    import_users(conn, write(tmp_path, "name,email\nOriginal,a@x.io\n"))
    stats = import_users(conn, write(tmp_path, "name,email\nChanged,A@X.io\n", "2.csv"))
    assert (stats.inserted, stats.rejected) == (0, 1)
    assert "already exists" in stats.rejections[0].reason
    assert conn.execute("SELECT name FROM users").fetchone()["name"] == "Original"


def test_upsert_mode_updates_or_leaves_unchanged(conn, tmp_path):
    import_users(conn, write(tmp_path, "name,email\nOriginal,a@x.io\nSame,b@x.io\n"))
    stats = import_users(
        conn,
        write(tmp_path, "name,email\nChanged,a@x.io\nSame,b@x.io\nNew,c@x.io\n", "2.csv"),
        mode="upsert",
    )
    assert (stats.updated, stats.unchanged, stats.inserted, stats.rejected) == (1, 1, 1, 0)
    names = {r["email"]: r["name"] for r in conn.execute("SELECT name, email FROM users")}
    assert names == {"a@x.io": "Changed", "b@x.io": "Same", "c@x.io": "New"}


def test_in_file_duplicate_first_wins_even_in_upsert(conn, tmp_path):
    stats = import_users(
        conn, write(tmp_path, "name,email\nFirst,a@x.io\nSecond,A@x.io\n"), mode="upsert"
    )
    assert stats.inserted == 1 and stats.rejected == 1
    assert conn.execute("SELECT name FROM users").fetchone()["name"] == "First"


def test_header_validation(conn, tmp_path):
    for text, part in [
        ("name\nA\n", "missing"),
        ("email,name\nA,b\n", "exactly"),
        ("name,email,name\n", "duplicate"),
        ("name,email,extra\nA,a@x.io,1\n", "exactly"),
    ]:
        with pytest.raises(InputError, match=part):
            import_users(conn, write(tmp_path, text))


def test_header_case_and_bom_tolerated(conn, tmp_path):
    p = tmp_path / "b.csv"
    p.write_bytes("\ufeff Name , EMAIL \nAda,ada@x.io\n".encode())
    assert import_users(conn, p).inserted == 1


def test_empty_and_missing_files(conn, tmp_path):
    with pytest.raises(InputError, match="empty"):
        import_users(conn, write(tmp_path, ""))
    with pytest.raises(InputError, match="empty"):
        import_users(conn, write(tmp_path, "  \n\n", "ws.csv"))
    with pytest.raises(InputError, match="does not exist"):
        import_users(conn, tmp_path / "nope.csv")


def test_header_only_file_imports_zero(conn, tmp_path):
    stats = import_users(conn, write(tmp_path, "name,email\n"))
    assert stats.total_rows == 0 and stats.inserted == 0


def test_bad_mode(conn, tmp_path):
    with pytest.raises(ConfigError):
        import_users(conn, write(tmp_path, "name,email\n"), mode="replace")  # type: ignore[arg-type]


def test_blank_and_short_rows_are_reported(conn, tmp_path):
    stats = import_users(conn, write(tmp_path, "name,email\nAda,ada@x.io\n\nOnlyName\nA,b,c\n"))
    assert stats.inserted == 1 and stats.rejected == 3
