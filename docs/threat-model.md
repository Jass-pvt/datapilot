# Lightweight Threat Model (STRIDE)

Scope: the CLI importers, the SQLite database and the local scores API in this repository.
Out of scope: the real Open Library service, the operating system, physical access to the machine.
This is a *lightweight* model written for an assessment. It lists risks that are mitigated and
those that remain; it does **not** claim all threats are eliminated.

Assets: integrity of the SQLite data; availability of the tools; personal data (names, e-mails);
the scores API.
Trust boundaries: (1) Open Library -> our HTTP client, (2) CSV file -> importer, (3) HTTP clients -> scores API,
(4) application -> SQLite file.

| # | STRIDE | Threat | Attack scenario | Impact | Mitigation | Test evidence |
|---|---|---|---|---|---|---|
| T1 | Tampering | Malformed / hostile JSON from the external API | API (or a man-in-the-middle) returns wrong shape, wrong types, huge strings | Corrupt rows, crashes | Structure check, pydantic schema per record, key regex, length/year limits, bad records stored in `failed_records` (excerpt capped at 200 chars); DB CHECK constraints as backstop | `tests/security/test_api_responses.py` (all), `tests/unit/test_books_models.py` |
| T2 | Denial of service | Slow, failing or rate-limiting API | Server returns 5xx/429 or hangs | Hung or hammering client | Timeout on every request, bounded retries (default 3), exponential back-off, `Retry-After` honoured (capped), client-side minimum interval, `pages <= 10`, `limit <= 100` | `tests/unit/test_books_client.py`, `tests/integration/test_books_ingest.py::test_parameter_validation` |
| T3 | Denial of service | Oversized API response | Multi-GB body or 100k records | Memory exhaustion | Body read in chunks and aborted at 2 MB; max 500 docs/page | `test_books_client.py::test_invalid_json_and_oversized_response`, `test_books_models.py::test_too_many_docs_rejected` |
| T4 | Tampering / DoS | Malicious CSV input | Binary file, NUL bytes, 10 MB file, million rows, giant field, wrong columns | Crash, memory use, bad data | UTF-8 decoding check, 5 MB / 100k row limits, csv field-size limit, strict header, per-row validation; every rejected row reported | `tests/security/test_csv_input.py`, `tests/integration/test_users_import.py` |
| T5 | Tampering (downstream) | CSV/formula injection | Name `=HYPERLINK(...)` is later opened in Excel from the rejected-rows file | Code/data exfiltration on the analyst's machine | Names with such characters rejected at validation; formula-leading cells prefixed with `'` when writing the rejected CSV | `test_csv_input.py::test_formula_cells_are_neutralised_in_rejected_file` |
| T6 | Tampering / Elevation | SQL injection | `Robert'); DROP TABLE users;--` in a title, name or e-mail | Data loss or disclosure | Every statement parameterised (`?`); no SQL built from input; allow-list name/e-mail validation (defence in depth) | `tests/security/test_sql_injection.py` |
| T7 | Tampering | Data corruption (partial write, duplicates, crash mid-run) | Crash after 40 of 100 inserts; same ingestion run 5x | Inconsistent or duplicated data | `UNIQUE(api_id)`, `UNIQUE(email)`, NOT NULL/CHECK/FK constraints; per-page and per-import transactions with ROLLBACK on any exception incl. `KeyboardInterrupt`; idempotent upsert | `tests/security/test_rollback_integrity.py`, `tests/unit/test_db.py` |
| T8 | Spoofing / Elevation | Unauthorised access to the scores API | Another local process or host reads `/scores` | Data disclosure | Optional API key (`LAB_API_KEY`) with constant-time compare; default bind `127.0.0.1` | `tests/security/test_api_access_control.py::test_api_key_required_when_configured` |
| T9 | Denial of service | Excessive requests to the scores API | Tight loop of requests | API unavailable | Per-client fixed-window rate limit returning 429 + `Retry-After` | `test_api_access_control.py::test_rate_limit_returns_429_then_recovers` |
| T10 | Information disclosure | Sensitive data / internals in logs and errors | Stack trace, SQL, file path or e-mail printed or logged | Leak of PII or internals | `LabError` messages are fixed strings; unexpected errors show a generic message and log only the exception *type*; log policy "events and counts, never record content" | `tests/security/test_error_messages_and_logs.py` |
| T11 | Repudiation | No record of what a run did | Disputed data origin | Weak accountability | `ingestion_runs` and `failed_records` tables record each run, its counts, status and errors | `tests/integration/test_books_ingest.py`, `test_rollback_integrity.py` (run status checks) |

## Residual risks and limitations (not mitigated)

* **No encryption at rest**: `data/lab.db` and the rejected-rows CSV contain plaintext e-mails. Protect with OS file permissions / disk encryption.
* **No user authentication for the CLI or the DB file**; anyone with file access can read or edit it.
* **TLS** relies on httpx's default certificate verification; there is no test for it.
* **API-key auth and the rate limiter** are minimal: one shared key, in-memory counters per process, keyed by client address (spoofable behind proxies). Not production-grade.
* **E-mail validation** is a pragmatic regex, not full RFC 5322; names with digits or unusual symbols are rejected (a documented policy that can reject real people).
* **Dependency supply chain** is not scanned in CI.
* **Concurrency**: `BEGIN IMMEDIATE` serialises writers, but multi-process behaviour is not load-tested.
* Live Open Library behaviour was **not** exercised in the build environment (network blocked); only mocked responses were tested.
