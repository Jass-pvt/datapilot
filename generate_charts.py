import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt

Path("artifacts").mkdir(exist_ok=True)
BLUE = "#4878A8"
RED = "#E05A5A"

# --- Chart 1: Books Ingestion Runs from SQLite ---
conn = sqlite3.connect("data/lab.db")
runs = conn.execute(
    "SELECT id, inserted, unchanged, failed FROM ingestion_runs ORDER BY id"
).fetchall()
conn.close()

run_labels = [f"Run {r[0]}" for r in runs]
inserted = [r[1] for r in runs]
unchanged = [r[2] for r in runs]

fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
x = range(len(run_labels))
w = 0.36
ax.bar([i - w / 2 for i in x], inserted, width=w, label="Inserted", color=BLUE)
ax.bar([i + w / 2 for i in x], unchanged, width=w, label="Unchanged (Idempotent)", color="#7BAFD4")
ax.set_title("Books Ingestion Runs (Idempotency Check)")
ax.set_xlabel("Ingestion Run")
ax.set_ylabel("Record Count")
ax.set_xticks(list(x))
ax.set_xticklabels(run_labels)
ax.legend()
fig.tight_layout()
fig.savefig("artifacts/books_runs.png")
plt.close(fig)

# --- Chart 2: CSV Users Import Breakdown ---
categories = ["Skip Mode\n(1st Run)", "Skip Mode\n(Re-run)", "Upsert Mode\n(Re-run)"]
ins_vals = [6, 0, 0]
unch_vals = [0, 0, 6]
rej_vals = [5, 11, 5]

fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
x2 = range(len(categories))
ax.bar(x2, ins_vals, width=0.5, label="Inserted", color=BLUE)
ax.bar(x2, unch_vals, width=0.5, bottom=ins_vals, label="Unchanged", color="#7BAFD4")
ax.bar(
    x2,
    rej_vals,
    width=0.5,
    bottom=[i + u for i, u in zip(ins_vals, unch_vals, strict=True)],
    label="Rejected",
    color=RED,
)
ax.set_title("CSV User Import Results by Mode (11 Total Rows)")
ax.set_ylabel("Row Count")
ax.set_xticks(list(x2))
ax.set_xticklabels(categories)
ax.set_ylim(0, 13)
ax.legend()
fig.tight_layout()
fig.savefig("artifacts/users_import.png")
plt.close(fig)

print("Saved: artifacts/books_runs.png, artifacts/users_import.png")
