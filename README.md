# Secure Data & AI Engineering Lab

A small, test-driven Python project that shows how external data can be **collected, validated,
stored, analysed and used safely**, built for the AccuKnox AI Security Engineer (New Grad)
assessment. It covers three modules (books ingestion, score analytics, CSV import), a security
layer with tests, and written AI/LLM security design documents.

> Status honesty: everything under "Implemented" ran in the author's build environment (Linux,
> Python 3.12) as described in *Verification status*. It has **not** been run on Windows by the
> assistant that generated it; run the commands below on your machine. Live Open Library
> access was **not** exercised in the build environment.

## 1. Overview

| Module | Official requirement | Where |
|---|---|---|
| Books ingestion | Fetch books from a REST API, store title/author/year in SQLite, display them | `src/lab/books/` |
| Score analytics | Fetch scores from an API, compute average, bar chart | `src/lab/scores/` |
| CSV importer | Read user CSV, insert into SQLite | `src/lab/users/` |

## 2. Architecture

```
            +-----------+       +-------------------+       +----------------+
 Open       | books/    |       | service.py        |       |                |
 Library -->| client.py |------>| validate (pydantic)|----->|   SQLite       |
 (HTTPS)    | retries,  |       | 1 txn per page    |       |  (db.py:       |
            | limits    |       +-------------------+       |  constraints,  |
            +-----------+                                   |  transactions) |
 users.csv --> users/importer.py (validate, dedupe, 1 txn) ->|                |
 scores.json / FastAPI --> scores/ (validate, stats, chart)  +----------------+
                         cli.py (argparse)  ·  logging_config.py (JSON logs)
```

**API id vs database id.** `books.api_id` (e.g. `OL45883W`) is assigned by Open Library and is the
*natural key* used for duplicate detection (`UNIQUE`). `books.id` is our own integer *surrogate key*
used for joins/foreign keys; it stays stable if the API changes its id format and is smaller and faster
to index.

## 3. Features

* Timeouts, bounded retries with exponential back-off, `Retry-After`, client-side rate limit
* Pydantic validation + normalisation; failed records stored and reported
* Idempotent ingestion (`UNIQUE` + upsert), one transaction per page, run statistics in `ingestion_runs`
* Score validation (strict), data-quality report, mean/median/min/max/std-dev, competition ranking, PNG chart with average line
* CSV importer: strict header, normalisation, duplicate policy, dry-run, upsert, rejected-rows CSV, all-or-nothing transaction
* JSON structured logging that never logs record content
* Optional API-key auth and rate limiting on the local scores API

## 4. Technology stack

Python 3.11+, SQLite (stdlib `sqlite3`), httpx, pydantic, FastAPI + uvicorn, matplotlib, pytest, pytest-cov, Ruff, GitHub Actions. No paid services, no accounts. Docker/Kubernetes deliberately omitted.

## 5-6. Installation (Windows PowerShell)

```powershell
cd secure-data-ai-lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

Environment variables (optional): `LAB_DB` (default `data/lab.db`), `LAB_API_KEY` (enables API-key auth on the scores API).

```powershell
$env:LAB_API_KEY = "change-me"        # PowerShell syntax
```

## 7. Execution commands

```powershell
python -m lab init-db

# Module 1 - books (needs internet; be polite to the public API)
python -m lab books fetch --query "python programming" --pages 2 --limit 20
python -m lab books list
python -m lab books stats

# Module 2 - scores (offline, reproducible sample)
python -m lab scores analyze                     # writes artifacts/student_scores.png
python -m lab scores serve                       # http://127.0.0.1:8000/scores (new terminal)
python -m lab scores analyze --source http://127.0.0.1:8000/scores

# Module 3 - users
python -m lab users import --csv data/sample_users.csv --dry-run
python -m lab users import --csv data/sample_users.csv
python -m lab users import --csv data/sample_users.csv --mode upsert
python -m lab users list
```

Add `--db some.db` (before the command) to use another database file, e.g. `python -m lab --db demo.db init-db`.

### Duplicate-email policy (users)
E-mails are trimmed and lower-cased. In a file the **first** row for an e-mail wins; later rows are
rejected and reported. Against the database: `skip` (default) rejects rows whose e-mail exists;
`upsert` updates the stored name if it differs (`updated`) or reports `unchanged`. Every non-inserted
row is counted and written to the rejected CSV (identical upsert rows are counted as `unchanged`).

### Score policies
Scores must be JSON numbers in 0-100; strings, booleans, null, NaN are rejected. Duplicate names
(case-insensitive): first wins. Ranking: standard competition ranking (1, 2, 2, 4).
Why the statistics: average (required), median (outlier-robust), min/max (range),
population std-dev (spread of the whole class).

## 8. Testing

```powershell
ruff check .
ruff format --check .
pytest                                  # 134 tests
pytest --cov --cov-report=term-missing  # coverage
pytest tests/security -v                # security tests only
```

Tests use temporary SQLite databases and mocked HTTP (`httpx.MockTransport`); none touch the network.

## 9. Security controls

See `docs/threat-model.md` for the full table (threat, scenario, impact, mitigation, test). Summary:
parameterised SQL everywhere; allow-list validation; DB constraints; transactions with rollback;
idempotency; size/row/time limits; bounded retries; formula-injection neutralisation; generic
user-facing errors; PII-free logs; optional API key + rate limit.

## 10. Threat model summary
11 threats across STRIDE (external API, malformed JSON, malicious CSV, SQL injection, corruption, DoS,
unauthorised access, log leakage). Residual risks are listed explicitly, including no encryption at rest.

## 11. Known limitations
* Live Open Library ingestion not verified in the build environment (mocked tests only).
* Strict name policy may reject legitimate names (digits, some symbols).
* One author per book (first listed); co-authors are not modelled.
* Rate limiter and API key are minimal and in-memory.
* Not run on Windows by the generator; CI is configured for Windows+Ubuntu but has not run yet.

## 12. Assumptions
* Open Library `search.json` returns `key`, `title`, `author_name`, `first_publish_year`.
* Publication years outside 1000..(current year + 1) are data errors and the record is rejected.
* The local scores API serves the sample file; real public score APIs are unreliable, hence a reproducible local one.

## 13. References
* Open Library Search API: https://openlibrary.org/dev/docs/api/search
* SQLite foreign keys / transactions / CHECK: https://www.sqlite.org/docs.html
* OWASP SQL Injection Prevention Cheat Sheet; OWASP CSV Injection
* Microsoft STRIDE threat modelling
* OWASP Top 10 for LLM Applications (see `docs/ai-security.md`)

## Repository layout
`src/lab/` code · `tests/{unit,integration,security}` · `data/` samples · `docs/` threat model, architecture, AI security, vector DB comparison, self-assessment guide, submission template · `.github/workflows/ci.yml`
