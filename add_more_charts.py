import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt

Path("artifacts").mkdir(exist_ok=True)
BLUE = "#4878A8"
TEAL = "#2E8B8B"
RED = "#E05A5A"

# --- Chart 3: Pytest Suite Breakdown (134 Passed Tests) ---
suites = [
    "Users Validation (Unit)",
    "Books Models (Unit)",
    "Books Ingestion (Int)",
    "Scores (Unit)",
    "CSV Security",
    "Books Client (Unit)",
    "DB (Unit)",
    "Rollback Integrity (Sec)",
    "SQL Injection (Sec)",
    "CLI (Int)",
    "API Responses (Sec)",
    "Scores API (Int)",
    "Error & Logs (Sec)",
    "API Access Control (Sec)",
    "Logging (Unit)",
]
counts = [23, 17, 13, 9, 8, 8, 7, 6, 9, 5, 5, 4, 4, 3, 1]

fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
y_pos = list(range(len(suites)))[::-1]
colors = [RED if "(Sec)" in s else BLUE for s in suites]
ax.barh(y_pos, counts, color=colors)
ax.set_yticks(y_pos)
ax.set_yticklabels(suites)
ax.set_xlabel("Passed Test Count (Total = 134)")
ax.set_title("Pytest Coverage Across Unit, Integration & Security Suites")
ax.set_xlim(0, 27)
for y, c in zip(y_pos, counts):
    ax.text(c + 0.4, y, str(c), va="center", fontsize=8.5)
fig.tight_layout()
fig.savefig("artifacts/test_suite_breakdown.png")
plt.close(fig)

# --- Chart 4: Books Catalog by Publication Decade (from SQLite) ---
conn = sqlite3.connect("data/lab.db")
years = [r[0] for r in conn.execute("SELECT year FROM books WHERE year IS NOT NULL").fetchall()]
conn.close()

decades = {}
for y in years:
    d = f"{(int(y) // 10) * 10}s"
    decades[d] = decades.get(d, 0) + 1

sorted_decades = sorted(decades.items())
labels = [k for k, _ in sorted_decades]
vals = [v for _, v in sorted_decades]

fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
bars = ax.bar(labels, vals, width=0.55, color=TEAL)
ax.set_title(f"Ingested Books by Publication Decade (Total = {len(years)} Books)")
ax.set_xlabel("Decade")
ax.set_ylabel("Number of Books")
ax.set_ylim(0, max(vals) + 4)
for bar, v in zip(bars, vals):
    ax.text(bar.get_x() + bar.get_width() / 2, v + 0.6, str(v), ha="center", fontsize=9)
fig.tight_layout()
fig.savefig("artifacts/books_by_decade.png")
plt.close(fig)

print("Saved: artifacts/test_suite_breakdown.png, artifacts/books_by_decade.png")
