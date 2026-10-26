"""Monitor scores by evidence view, one row per monitor model.

    python analysis/hongbee/merged/bench/plot_views.py  ->  analysis/hongbee/figures/monitor_views_by_model.{png,svg,pdf}

Thresholds are the ones evaluate.py picks on split A.
"""
import json
import random
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "figures"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#c3c2b7"})
VIEWS = [("text", "Messages only"), ("actions", "Actions only"), ("raw", "Messages + actions"), ("structured", "Structured report")]
CASES = [("coordinated", "Coordinated\nrelaxation", "#2a78d6"), ("talk_only", "Talk without\naction", "#eb6834"),
         ("solo", "Same incentive,\nno agreement", "#1baf7a"), ("harm_alone", "Harm without\nagreement", "#6250d6"),
         ("legit", "Legitimate\napproval", "#898781")]
MODELS = [("gpt-5.4-mini", "GPT-5.4 mini"), ("gpt-5.4", "GPT-5.4")]

S = {s["uid"]: s for s in map(json.loads, open(HERE / "set.jsonl"))}
random.seed(1)
fig, axes = plt.subplots(len(MODELS), 4, figsize=(11, 3.7 * len(MODELS)), sharey=True, sharex=True)
fig.patch.set_facecolor("white")
for r, (key, name) in enumerate(MODELS):
    rows = [m for m in map(json.loads, open(HERE / f"monitor_{key}.jsonl")) if m.get("score") is not None]
    thr = {v: x["threshold_from_A"] for v, x in json.load(open(HERE / f"eval_monitor_{key}.json")).items()}
    for c_, (v, title) in enumerate(VIEWS):
        ax = axes[r][c_]
        for i, (c, _, col) in enumerate(CASES):
            y = len(CASES) - 1 - i
            ax.axhspan(y - 0.42, y + 0.42, color=col, alpha=0.08, lw=0)
            xs = [m["score"] for m in rows if m["view"] == v and S[m["uid"]]["case"] == c]
            ax.scatter(xs, [y + random.uniform(-0.28, 0.28) for _ in xs], s=14, color=col, alpha=0.75,
                       edgecolor="white", linewidth=0.5, zorder=3)
            mean = st.mean(xs)
            ax.plot([mean, mean], [y - 0.38, y + 0.38], color=col, lw=2.6, solid_capstyle="round", zorder=4)
        ax.axvline(thr[v], color="#0b0b0b", lw=0.9, ls=(0, (3, 3)), zorder=2)
        ax.set_xlim(-3, 103)
        ax.set_xticks([0, 50, 100])
        ax.set_ylim(-0.6, len(CASES) - 0.4)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.tick_params(axis="x", colors="#52514e")
        if r == 0:
            ax.set_title(title, fontsize=10, color="#0b0b0b", pad=8)
    axes[r][0].set_yticks(range(len(CASES)))
    axes[r][0].set_yticklabels([lab for _, lab, _ in CASES][::-1])
    axes[r][0].annotate(name, xy=(-0.62, 0.5), xycoords="axes fraction", rotation=90, ha="center", va="center",
                        fontsize=11, fontweight="bold", color="#0b0b0b")
fig.supxlabel("Monitor score: did coordination drive this decision? (0–100)", fontsize=9, color="#52514e", y=0.015)
fig.text(0.995, 0.01, "dots: decisions   bar: mean   dashed: threshold fixed on split A", ha="right", fontsize=7.5, color="#898781")
fig.tight_layout(rect=(0.02, 0.03, 1, 1))
OUT.mkdir(exist_ok=True)
for ext in ("png", "svg", "pdf"):
    fig.savefig(OUT / f"monitor_views_by_model.{ext}", dpi=200, facecolor="white")
print("saved", OUT / "monitor_views_by_model.png")
