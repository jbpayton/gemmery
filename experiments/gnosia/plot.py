"""Graphs for the scaled Gnosia experiment.
Run: .venv/bin/python experiments/gnosia/plot.py
"""
import json
import random
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from engine import make_pool, run_game, cold_detector, memory_detector, build_profiles  # noqa: E402


def learning_curve(n=400, window=30):
    pool = make_pool(24); rng = random.Random(7)
    games = [run_game(s, pool, 8, 2) for s in range(n)]
    xs, mem, cold = [], [], []
    mh, ch = [], []
    for k, g in enumerate(games):
        mh.append(memory_detector(g, build_profiles(games[:k]), rng) in g.gnosia_set())
        ch.append(cold_detector(g, rng) in g.gnosia_set())
        if k >= window:
            xs.append(k); mem.append(sum(mh[k-window:k])/window); cold.append(sum(ch[k-window:k])/window)
    plt.figure(figsize=(8, 4.5))
    plt.plot(xs, mem, lw=2.2, color="#1f77b4", label="memory (per-persona tells)")
    plt.plot(xs, cold, lw=2.2, color="#d62728", label="memoryless")
    plt.axhline(0.25, ls="--", c="gray", lw=1, label="chance (2 of 8)")
    plt.ylim(0, 1); plt.xlabel("games of history"); plt.ylabel(f"Gnosia-ID accuracy (rolling {window})")
    plt.title("Gnosia (24-persona pool): tells are learnable from history")
    plt.legend(fontsize=9); plt.grid(alpha=0.25); plt.tight_layout()
    plt.savefig(ROOT / "learning_curve.png", dpi=130); print("wrote learning_curve.png")


def arm_comparison():
    from score import rows, truth, GIDS  # reuse scorer's parsing
    arms = [("cold", "no memory\n(cold)", "#d62728"),
            ("md", "plain .md\n(dump all 24)", "#ff7f0e"),
            ("gemmery", "Gemmery\n(retrieve 8)", "#1f77b4")]
    labels, vals, colors = [], [], []
    for key, lab, col in arms:
        p = rows[key]
        if not p:
            continue
        acc = sum(p.get(g) in truth[g] for g in GIDS) / len(GIDS)
        labels.append(lab); vals.append(acc); colors.append(col)
    plt.figure(figsize=(6.5, 4.5))
    bars = plt.bar(labels, vals, color=colors, width=0.6)
    plt.axhline(0.25, ls="--", c="gray", lw=1)
    for b, v in zip(bars, vals):
        plt.text(b.get_x()+b.get_width()/2, v+0.02, f"{v:.2f}", ha="center", fontweight="bold")
    plt.ylim(0, 1.05); plt.ylabel(f"Gnosia-ID accuracy (LLM, n={len(GIDS)})")
    plt.title("Scaled memory: does selective retrieval beat dump-everything?")
    plt.tight_layout(); plt.savefig(ROOT / "arm_comparison.png", dpi=130)
    print("wrote arm_comparison.png")


if __name__ == "__main__":
    learning_curve()
    try:
        arm_comparison()
    except Exception as e:
        print("arm_comparison skipped:", e)
