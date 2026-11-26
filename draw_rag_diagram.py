from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

Path("artifacts").mkdir(exist_ok=True)

fig, ax = plt.subplots(figsize=(10, 4.2), dpi=150)
ax.set_xlim(0, 100)
ax.set_ylim(0, 42)
ax.axis("off")

boxes = [
    (3, 24, 18, 11, "#E8EEF5", "#4878A8", "1. Documents\n& Chunking"),
    (28, 24, 18, 11, "#E8EEF5", "#4878A8", "2. Embeddings\n& Vector Index"),
    (53, 24, 19, 11, "#E6F2F2", "#2E8B8B", "3. Similarity\nSearch (Top-K)"),
    (79, 24, 18, 11, "#F4ECF7", "#7D4E9E", "4. LLM + Context\n& Guardrails"),
    (
        28,
        6,
        44,
        10,
        "#FDEDEC",
        "#C0392B",
        "Cross-Cutting Controls: Input Validation, Auth, Rate Limit & PII-Free Logs",
    ),
]

for x, y, w, h, fc, ec, text in boxes:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.6,rounding_size=1.5",
        facecolor=fc,
        edgecolor=ec,
        linewidth=1.5,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=8.5,
        color="#1F2933",
        fontweight="medium",
    )

arrows = [(21.6, 29.5, 5.8), (46.6, 29.5, 5.8), (72.6, 29.5, 5.8)]
for ax_x, ax_y, dx in arrows:
    ax.annotate(
        "",
        xy=(ax_x + dx, ax_y),
        xytext=(ax_x, ax_y),
        arrowprops=dict(arrowstyle="->", lw=1.6, color="#374151"),
    )

ax.set_title(
    "RAG Retrieval & AI Security Architecture Overview", fontsize=11, fontweight="bold", pad=8
)
fig.tight_layout()
fig.savefig("artifacts/rag_architecture.png")
plt.close(fig)
print("Saved: artifacts/rag_architecture.png")
