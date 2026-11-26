"""Command-line interface.

Examples::

    python -m lab init-db
    python -m lab books fetch --query "python programming" --pages 2
    python -m lab books list
    python -m lab books stats
    python -m lab scores analyze
    python -m lab scores serve
    python -m lab users import --csv data/sample_users.csv --dry-run
"""

import argparse
import json
import logging
import os
import sys
from collections.abc import Sequence

from lab.books.client import OpenLibraryClient
from lab.books.repository import database_stats, list_books
from lab.books.service import ingest_books
from lab.db import connect, init_db
from lab.errors import LabError
from lab.logging_config import setup_logging
from lab.scores.chart import create_bar_chart
from lab.scores.client import load_scores
from lab.scores.models import extract_records, validate_records
from lab.scores.stats import compute_stats, rank_students
from lab.users.importer import import_users, list_users

logger = logging.getLogger("lab.cli")
DEFAULT_DB = os.environ.get("LAB_DB", "data/lab.db")


def _open(args: argparse.Namespace):
    conn = connect(args.db)
    init_db(conn)
    return conn


def cmd_init_db(args: argparse.Namespace) -> int:
    _open(args).close()
    print(f"Database ready: {args.db}")
    return 0


def cmd_books_fetch(args: argparse.Namespace) -> int:
    conn = _open(args)
    with OpenLibraryClient(min_interval=args.min_interval) as client:
        stats = ingest_books(conn, client, args.query, pages=args.pages, limit=args.limit)
    print(json.dumps(stats.__dict__, indent=2))
    return 0 if stats.status == "completed" else 1


def cmd_books_list(args: argparse.Namespace) -> int:
    rows = list_books(_open(args), args.limit)
    if not rows:
        print("No books stored yet. Run: python -m lab books fetch --query <text>")
        return 0
    print(f"{'ID':>4}  {'API ID':<14} {'YEAR':<5} {'AUTHOR':<28} TITLE")
    for r in rows:
        year = r["publication_year"] if r["publication_year"] is not None else "-"
        author = (r["author"] or "(unknown)")[:27]
        print(f"{r['id']:>4}  {r['api_id']:<14} {year!s:<5} {author:<28} {r['title']}")
    return 0


def cmd_books_stats(args: argparse.Namespace) -> int:
    print(json.dumps(database_stats(_open(args)), indent=2))
    return 0


def cmd_scores_analyze(args: argparse.Namespace) -> int:
    records, report = validate_records(extract_records(load_scores(args.source)))
    stats = compute_stats(records)
    print(
        f"Records: total={report.total} valid={report.valid} invalid={report.invalid} "
        f"(duplicates={report.duplicates})"
    )
    for index, reason in report.rejected:
        print(f"  rejected record {index}: {reason}")
    if stats is None:
        print("No valid scores: no statistics or chart produced.")
        return 2
    print(
        f"Average: {stats.average:.2f}  Median: {stats.median:.2f}  "
        f"Min: {stats.minimum:.2f}  Max: {stats.maximum:.2f}  StdDev: {stats.std_dev:.2f}"
    )
    print("Ranking (ties share a rank, next rank is skipped):")
    for rank, rec in rank_students(records):
        print(f"  {rank:>2}. {rec.name} - {rec.score:g}")
    path = create_bar_chart(records, args.output)
    print(f"Chart saved: {path}")
    return 0


def cmd_scores_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from lab.scores.api import create_app

    uvicorn.run(create_app(args.data), host=args.host, port=args.port)
    return 0


def cmd_users_import(args: argparse.Namespace) -> int:
    conn = _open(args)
    stats = import_users(
        conn, args.csv, mode=args.mode, dry_run=args.dry_run, rejected_path=args.rejected
    )
    label = "DRY RUN (nothing saved)" if stats.dry_run else "COMMITTED"
    print(f"{label} mode={stats.mode}")
    print(
        f"rows={stats.total_rows} inserted={stats.inserted} updated={stats.updated} "
        f"unchanged={stats.unchanged} rejected={stats.rejected}"
    )
    for item in stats.rejections:
        print(f"  row {item.row_number}: {item.reason}")
    if args.rejected:
        print(f"Rejected rows written to: {args.rejected}")
    return 0


def cmd_users_list(args: argparse.Namespace) -> int:
    for r in list_users(_open(args), args.limit):
        print(f"{r['id']:>4}  {r['email']:<32} {r['name']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lab", description="Secure Data & AI Engineering Lab")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite file (default: data/lab.db)")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create the database schema").set_defaults(func=cmd_init_db)

    books = sub.add_parser("books", help="Open Library ingestion").add_subparsers(
        dest="action", required=True
    )
    fetch = books.add_parser("fetch", help="fetch and store books")
    fetch.add_argument("--query", required=True)
    fetch.add_argument("--pages", type=int, default=1)
    fetch.add_argument("--limit", type=int, default=20)
    fetch.add_argument("--min-interval", type=float, default=1.0, help="seconds between requests")
    fetch.set_defaults(func=cmd_books_fetch)
    blist = books.add_parser("list", help="display stored books")
    blist.add_argument("--limit", type=int, default=50)
    blist.set_defaults(func=cmd_books_list)
    books.add_parser("stats", help="database and ingestion statistics").set_defaults(
        func=cmd_books_stats
    )

    scores = sub.add_parser("scores", help="student score analytics").add_subparsers(
        dest="action", required=True
    )
    analyze = scores.add_parser("analyze", help="validate, summarise and chart scores")
    analyze.add_argument(
        "--source", default="data/sample_scores.json", help="file path or http(s) URL"
    )
    analyze.add_argument("--output", default="artifacts/student_scores.png")
    analyze.set_defaults(func=cmd_scores_analyze)
    serve = scores.add_parser("serve", help="serve sample scores on a local FastAPI app")
    serve.add_argument("--data", default="data/sample_scores.json")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_scores_serve)

    users = sub.add_parser("users", help="CSV user importer").add_subparsers(
        dest="action", required=True
    )
    imp = users.add_parser("import", help="import users from CSV")
    imp.add_argument("--csv", required=True)
    imp.add_argument("--mode", choices=["skip", "upsert"], default="skip")
    imp.add_argument("--dry-run", action="store_true")
    imp.add_argument("--rejected", default="artifacts/rejected_users.csv")
    imp.set_defaults(func=cmd_users_import)
    ulist = users.add_parser("list", help="display stored users")
    ulist.add_argument("--limit", type=int, default=50)
    ulist.set_defaults(func=cmd_users_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level)
    try:
        return args.func(args)
    except LabError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Log only the exception TYPE; never echo internals or input to the user.
        logger.error("unexpected_error", extra={"error_type": type(exc).__name__})
        print("error: an unexpected internal error occurred (see log)", file=sys.stderr)
        return 2
