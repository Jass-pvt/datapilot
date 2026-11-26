"""Bar chart of student scores with an average reference line."""

from pathlib import Path

from matplotlib.figure import Figure

from lab.scores.models import ScoreRecord
from lab.scores.stats import compute_stats


def create_bar_chart(records: list[ScoreRecord], output_path: str | Path) -> Path | None:
    """Save a PNG and return its path, or return ``None`` when there is no data.

    Uses matplotlib's object API (``Figure``) instead of ``pyplot`` so no global GUI
    state or display is needed (works headless, e.g. in CI).
    """
    stats = compute_stats(records)
    if stats is None:
        return None

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    ordered = sorted(records, key=lambda r: (-r.score, r.name.casefold()))
    fig = Figure(figsize=(max(6.0, 0.7 * len(ordered) + 2), 5.0))
    ax = fig.subplots()
    ax.bar([r.name for r in ordered], [r.score for r in ordered], color="#4C78A8")
    ax.axhline(
        stats.average,
        color="#E45756",
        linestyle="--",
        linewidth=1.5,
        label=f"Average: {stats.average:.2f}",
    )
    ax.set_title("Student Scores")
    ax.set_xlabel("Student")
    ax.set_ylabel("Score (0-100)")
    ax.set_ylim(0, 100)
    ax.tick_params(axis="x", labelrotation=45)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=150, format="png")
    return path
