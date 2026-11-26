"""Hostile or oversized CSV input is rejected safely with clear, generic errors."""

import csv

import pytest

from lab.errors import InputError
from lab.users.importer import import_users


def test_binary_garbage_is_rejected(conn, tmp_path):
    p = tmp_path / "g.csv"
    p.write_bytes(b"\xff\xfe\x00\x01garbage\x80\x81")
    with pytest.raises(InputError, match="UTF-8"):
        import_users(conn, p)


def test_oversized_file_is_rejected(conn, tmp_path):
    p = tmp_path / "big.csv"
    p.write_text("name,email\n" + "Ada,ada@x.io\n" * 100)
    with pytest.raises(InputError, match="too large"):
        import_users(conn, p, max_bytes=100)


def test_too_many_rows_are_rejected(conn, tmp_path):
    p = tmp_path / "rows.csv"
    p.write_text("name,email\n" + "".join(f"U,u{i}@x.io\n" for i in range(20)))
    with pytest.raises(InputError, match="too many rows"):
        import_users(conn, p, max_rows=10)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_oversized_field_is_rejected(conn, tmp_path):
    p = tmp_path / "field.csv"
    p.write_text("name,email\n" + "A" * (csv.field_size_limit() + 10) + ",a@x.io\n")
    with pytest.raises(InputError, match="malformed"):
        import_users(conn, p)


def test_overlong_values_become_row_rejections(conn, tmp_path):
    p = tmp_path / "long.csv"
    p.write_text(f"name,email\n{'A' * 101},a@x.io\nOk,{'a' * 250}@x.io\n")
    stats = import_users(conn, p)
    assert stats.inserted == 0 and stats.rejected == 2


def test_header_injection_style_input_rejected(conn, tmp_path):
    p = tmp_path / "h.csv"
    p.write_text("name,email\nAda,ada@x.io\nBob,bob@x.io\nBcc: evil@x.io\n")
    stats = import_users(conn, p)
    assert stats.inserted == 2 and stats.rejected == 1


def test_formula_cells_are_neutralised_in_rejected_file(conn, tmp_path):
    p = tmp_path / "f.csv"
    p.write_text('name,email\n"=HYPERLINK(""http://x.invalid"")",f@x.io\n')
    rej = tmp_path / "rej.csv"
    import_users(conn, p, rejected_path=rej)
    cell = list(csv.DictReader(rej.open(encoding="utf-8")))[0]["name"]
    assert cell.startswith("'=") and not cell.startswith("=")


def test_embedded_nul_does_not_crash(conn, tmp_path):
    p = tmp_path / "nul.csv"
    p.write_bytes(b"name,email\nAda\x00Evil,ada@x.io\n")
    try:
        stats = import_users(conn, p)
    except InputError:
        return  # rejected at file level is acceptable
    assert stats.rejected + stats.inserted == 1
