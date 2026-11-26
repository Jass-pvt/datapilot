# AccuKnox Assessment: Submission Workbook

**Read first.** The assessment prohibits copied AI answers. This file is a *structure and fact sheet*.
Items marked **[YOU WRITE]** must be written by you, in your own words, after you understand them.
The exact official question wording was not provided to the assistant that generated this file; the
headings below are paraphrases. **Paste the exact official questions** under each heading.

---

## Assignment 1: Python and database

### 1.1 Books API (official wording: [paste])
Facts you can build your answer on (verified by running the code in the build environment):
* Mocked-API tests prove: retries are bounded, back-off doubles, bad records go to `failed_records`, re-running creates no duplicates.
* **Not verified**: a live call to Open Library (network was blocked in the build environment). Run `python -m lab books fetch --query "python programming"` yourself and record the real output here: **[YOU PASTE REAL OUTPUT]**.

### 1.2 Student scores (official wording: [paste])
Observed on the bundled sample file (`python -m lab scores analyze`): total records 13, valid 8,
invalid 5 (1 duplicate), **average 81.94**, median 81.75, min 64, max 99. Chart: `artifacts/student_scores.png`.
Re-run on your machine and copy *your* observed numbers: **[YOU PASTE]**.

### 1.3 CSV importer (official wording: [paste])
Observed on `data/sample_users.csv`: 11 rows, 6 inserted, 5 rejected (invalid e-mail, in-file duplicate, empty name, two disallowed-character names). Re-run and confirm: **[YOU PASTE]**.

### 1.4 Code links
Push the repository to your own GitHub account first, then fill in. Do not use links you have not opened.

| Item | Suggested file (from this project) | Why it is a good choice | Your verified URL |
|---|---|---|---|
| Most complex **Python** code | `src/lab/users/importer.py` (alternatively `src/lab/books/service.py`) | Validation pipeline, duplicate policy, dry-run via rollback, error handling, 100% test coverage in the build run | **[https://github.com/&lt;you&gt;/&lt;repo&gt;/blob/main/src/lab/users/importer.py]** |
| Most complex **database** code | `src/lab/db.py` (schema, constraints, transaction helper) and `src/lab/books/repository.py` | Normalised schema, UNIQUE/CHECK/FK, indexes, idempotent upsert, parameterised SQL | **[https://github.com/&lt;you&gt;/&lt;repo&gt;/blob/main/src/lab/db.py]** |

Ownership: these files were generated with AI assistance for you. Submit them only if you can explain
every line, and follow the assessment's rules on AI help. If you have **older repositories you wrote
yourself** with strong Python/SQL, prefer those (I could not inspect any, so I cannot recommend specific files).

### 1.5 Be ready to answer (interview)
1. Why both `api_id` and `id`? 2. What stops duplicates if Python code has a bug? 3. What state is the DB in after a crash mid-page? 4. Why `BEGIN IMMEDIATE`? 5. Why is the dry run a rollback instead of skipping the inserts? 6. Why are SQL payload names rejected *and* safe? 7. What does `PRAGMA foreign_keys` default to? 8. Why population std-dev? 9. What is competition ranking?

---

## Assignment 2: AI and LLM fundamentals

### 2.1 Self-rating: LLM / Deep Learning / AI / ML
**[YOU WRITE]** Use `docs/ai-self-assessment.md`. Ratings I chose for you: none.

### 2.2 Chatbot architecture
Material: `docs/architecture.md` (diagram + request lifecycle) and `docs/ai-security.md`.
**[YOU WRITE]** a concise answer in your own words; include the diagram and be ready to explain why ACLs are enforced in the retrieval query and re-checked.

### 2.3 Vector databases
Material: `docs/vector-database-comparison.md`. Re-verify feature claims against current vendor docs.
**[YOU WRITE]** your own recommendation and justification for your scenario.

---

## Assignment 3: Project you are proud of

### What I could and could not verify
I read the **public README** of https://github.com/Jass-pvt/talentlens-ai. I did **not** read its
source code, tests or commit history, so I cannot confirm that the README matches the code.

What the README states (verify each against your code before using it):
* A CLI that screens PDF resumes for an AI/Python internship: deterministic eligibility, evidence classification, 100-point scoring, optional bounded LLM pass, GitHub enrichment, ranked JSON output.
* Per-file failure isolation, SHA-256 duplicate detection, parsing limits (10 MB, 15 pages), in-memory GitHub cache with a 4-thread pool, mocked-HTTP tests.
* Its own limitations section says: live GitHub and live LLM paths were tested only with mocked HTTP; no OCR; regex signals can miss paraphrases; weights are hand-tuned, not calibrated.

Do **not** cite numbers from the README (e.g. test counts) unless you have just re-run them.

### Candidate difficulty themes (a starting point, not your answer)
These are the hardest-sounding problems *according to the README*. Confirm in your code which are real, and pick the three you can explain:
1. Telling real evidence from keyword stuffing (evidence levels, skills-list-only vs implemented in a project) using deterministic rules.
2. Keeping an optional LLM from controlling decisions (bounded influence, schema validation, fallback, prompt-injection handling of untrusted resume text).
3. Processing untrusted, messy inputs reliably (corrupt/blank PDFs, per-file isolation, GitHub rate limits and caching).

### The exactly-three-lines answer
**[YOU WRITE]** Three lines, one concrete technical difficulty each, true to your implementation, no invented metrics.
Line 1: **[...]**  Line 2: **[...]**  Line 3: **[...]**

Questions to answer for yourself first (do this before writing): What did you implement versus plan? Which bug took longest? What would break on real resumes? What did you test, and what did you only mock?

### Project link
**[https://github.com/Jass-pvt/talentlens-ai]** (this URL was reachable when checked; confirm before submitting).

---

## Pre-submission checklist
- [ ] Repository pushed; every link opened in a private browser window
- [ ] Ran `ruff check .` and `pytest` on your own machine and recorded the real output
- [ ] Ran each CLI command on Windows PowerShell
- [ ] Live `books fetch` run at least once (output saved)
- [ ] CI run on GitHub is green (the workflow has not run yet)
- [ ] Every **[YOU WRITE]** item written by you
- [ ] You can explain every file in `src/lab/`
