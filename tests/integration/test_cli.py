from pathlib import Path

from lab.cli import main

ROOT = Path(__file__).resolve().parents[2]


def run(tmp_path, *args):
    return main(["--db", str(tmp_path / "t.db"), "--log-level", "ERROR", *args])


def test_init_and_empty_listing(tmp_path, capsys):
    assert run(tmp_path, "init-db") == 0
    assert run(tmp_path, "books", "list") == 0
    assert "No books stored" in capsys.readouterr().out
    assert run(tmp_path, "books", "stats") == 0


def test_users_import_and_list(tmp_path, capsys):
    rej = tmp_path / "rej.csv"
    code = run(
        tmp_path,
        "users",
        "import",
        "--csv",
        str(ROOT / "data/sample_users.csv"),
        "--rejected",
        str(rej),
    )
    out = capsys.readouterr().out
    assert code == 0 and "inserted=6" in out and rej.exists()
    run(tmp_path, "users", "list")
    assert "alice@example.com" in capsys.readouterr().out


def test_scores_analyze_writes_chart(tmp_path, capsys):
    png = tmp_path / "chart.png"
    code = run(
        tmp_path,
        "scores",
        "analyze",
        "--source",
        str(ROOT / "data/sample_scores.json"),
        "--output",
        str(png),
    )
    out = capsys.readouterr().out
    assert code == 0 and "Average: 81.94" in out and png.read_bytes().startswith(b"\x89PNG")


def test_scores_analyze_empty_returns_2(tmp_path, capsys):
    src = tmp_path / "e.json"
    src.write_text('{"students": []}')
    assert (
        run(
            tmp_path, "scores", "analyze", "--source", str(src), "--output", str(tmp_path / "c.png")
        )
        == 2
    )
    assert not (tmp_path / "c.png").exists()


def test_user_facing_error_exit_code(tmp_path, capsys):
    assert run(tmp_path, "users", "import", "--csv", str(tmp_path / "none.csv")) == 1
    assert "does not exist" in capsys.readouterr().err
