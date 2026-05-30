#!/usr/bin/env python3
"""Generate the figures used in the final report from ``data/eval_results.json``.

    python -m report.make_figures            # writes PNGs into report/figures/

Reads the evaluation output and produces:
    fig_corpus.png      corpus composition by file category
    fig_ablation.png    2x2 ablation bar chart (P@10 / MAP / NDCG@10)
    fig_sweeps.png      hyper-parameter sweeps (PRF k, PRF beta, boost gamma)
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = Path("data/eval_results.json")
OUT = Path("report/figures")


def main() -> int:
    data = json.loads(RESULTS.read_text())
    OUT.mkdir(parents=True, exist_ok=True)

    # --- corpus composition ---
    cats = data["corpus"]["by_category"]
    fig, ax = plt.subplots(figsize=(5, 3.2))
    items = sorted(cats.items(), key=lambda kv: kv[1], reverse=True)
    ax.bar([k for k, _ in items], [v for _, v in items], color="#4C72B0")
    ax.set_ylabel("documents")
    ax.set_title(f"Corpus composition ({data['corpus']['n_documents']} documents)")
    for i, (_, v) in enumerate(items):
        ax.text(i, v + 3, str(v), ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_corpus.png", dpi=150)
    plt.close(fig)

    # --- ablation ---
    abl = data["ablation"]
    order = ["baseline", "boost_only", "prf_only", "full"]
    labels = ["Baseline", "+Boost", "+PRF", "Full"]
    metrics = ["P@10", "MAP", "NDCG@10"]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    x = range(len(order))
    width = 0.25
    colors = ["#4C72B0", "#DD8452", "#55A868"]
    for j, m in enumerate(metrics):
        vals = [abl[v][m] for v in order]
        ax.bar([i + (j - 1) * width for i in x], vals, width, label=m, color=colors[j])
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylim(0.5, 0.82)
    ax.set_ylabel("score")
    ax.set_title("2x2 ablation: effect of PRF and file-type boost")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_ablation.png", dpi=150)
    plt.close(fig)

    # --- hyper-parameter sweeps ---
    sw = data["grid_search"]["sweeps"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.0))
    panels = [("prf_k", "PRF top-k"), ("prf_beta", "PRF β"), ("boost_gamma", "boost γ")]
    for ax, (key, title) in zip(axes, panels):
        rows = sw[key]
        xs = [r[key] for r in rows]
        ax.plot(xs, [r["MAP"] for r in rows], "o-", label="MAP", color="#DD8452")
        ax.plot(xs, [r["P@10"] for r in rows], "s--", label="P@10", color="#4C72B0")
        ax.plot(xs, [r["NDCG@10"] for r in rows], "^:", label="NDCG@10", color="#55A868")
        ax.set_title(title)
        ax.set_xlabel(key)
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("score")
    axes[-1].legend(fontsize=7, loc="best")
    fig.suptitle("Effect of hyper-parameters (other parameters held at defaults)")
    fig.tight_layout()
    fig.savefig(OUT / "fig_sweeps.png", dpi=150)
    plt.close(fig)

    _architecture_figure()

    print(f"Wrote figures to {OUT}/: fig_corpus.png, fig_ablation.png, "
          f"fig_sweeps.png, fig_architecture.png")
    return 0


def _box(ax, xy, w, h, text, color):
    from matplotlib.patches import FancyBboxPatch
    x, y = xy
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                                linewidth=1.2, edgecolor="#333", facecolor=color))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5)


def _arrow(ax, p0, p1):
    ax.annotate("", xy=p1, xytext=p0,
                arrowprops=dict(arrowstyle="-|>", color="#333", lw=1.2))


def _architecture_figure() -> None:
    """A block diagram of the indexing (offline) and query (online) pipelines."""
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 52)
    ax.axis("off")

    blue, green, orange, grey = "#cfe0f3", "#cfead8", "#f7ddc6", "#e8e8e8"

    # Offline indexing row (top)
    ax.text(2, 49, "Indexing (offline)", fontsize=9, weight="bold", color="#555")
    _box(ax, (2, 38), 17, 8, "Corpus\n(txt/html/pdf/\ncode/ipynb)", grey)
    _box(ax, (24, 38), 17, 8, "Parsers\nextract text", blue)
    _box(ax, (46, 38), 17, 8, "Analyze\ntokenize→stop→\nPorter stem", blue)
    _box(ax, (68, 38), 28, 8, "Inverted index +\ncosine-normalized\nTF-IDF vectors", green)
    for x0, x1 in [(19, 24), (41, 46), (63, 68)]:
        _arrow(ax, (x0, 42), (x1, 42))

    # Online query row (bottom)
    ax.text(2, 28, "Query (online)", fontsize=9, weight="bold", color="#555")
    _box(ax, (2, 16), 17, 8, "Query\nstring", grey)
    _box(ax, (24, 16), 17, 8, "Analyze\n(same pipeline)", blue)
    _box(ax, (24, 4), 17, 7, "Intent classifier\ncode/prose/neutral", orange)
    _box(ax, (46, 16), 17, 8, "Cosine\nranking", green)
    _box(ax, (68, 16), 13, 8, "Rocchio\nPRF\n[--prf]", orange)
    _box(ax, (83, 16), 13, 8, "File-type\nboost\n[--boost]", orange)
    _arrow(ax, (19, 20), (24, 20))
    _arrow(ax, (41, 20), (46, 20))
    _arrow(ax, (63, 20), (68, 20))
    _arrow(ax, (81, 20), (83, 20))
    _arrow(ax, (32, 16), (32, 11.2))           # query -> intent
    _arrow(ax, (41, 7.5), (89, 15.8))          # intent -> boost
    _arrow(ax, (82, 38), (74.5, 24))           # index -> cosine (shared vectors)
    ax.text(96.5, 20, "ranked\nresults", fontsize=8.5, va="center")
    _arrow(ax, (96, 20), (99.5, 20))

    fig.tight_layout()
    fig.savefig(OUT / "fig_architecture.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
