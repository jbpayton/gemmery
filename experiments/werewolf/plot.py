"""Graphs for the adversarial-memory (Werewolf) experiment.

Run with the venv python (matplotlib):  .venv/bin/python experiments/werewolf/plot.py
Produces:
  * learning_curve.png  — memory vs memoryless detector as history accumulates
                          (deterministic, 300 games — the statistical backbone)
  * arm_comparison.png  — LLM focal accuracy by memory backend (cold / .md / Gemmery)
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
from engine import run_game, cold_detector, memory_detector, build_profiles  # noqa: E402


def learning_curve(n=300, window=25):
    rng = random.Random(1)
    games = [run_game(s) for s in range(n)]
    xs, mem_w, cold_w = [], [], []
    mem_hits, cold_hits = [], []
    for k, g in enumerate(games):
        prof = build_profiles(games[:k])
        mem_hits.append(memory_detector(g, prof, rng) == g.wolf)
        cold_hits.append(cold_detector(g, rng) == g.wolf)
        if k >= window:
            xs.append(k)
            mem_w.append(sum(mem_hits[k - window:k]) / window)
            cold_w.append(sum(cold_hits[k - window:k]) / window)

    plt.figure(figsize=(8, 4.5))
    plt.plot(xs, mem_w, label="memory (learns each player's baseline)", lw=2.2, color="#1f77b4")
    plt.plot(xs, cold_w, label="memoryless (trapped by fake tells)", lw=2.2, color="#d62728")
    plt.axhline(0.25, ls="--", c="gray", lw=1, label="chance (1 of 4)")
    plt.ylim(-0.02, 1.02)
    plt.xlabel("games of history accumulated")
    plt.ylabel(f"wolf-ID accuracy (rolling, window={window})")
    plt.title("Werewolf: memory of past games makes tells readable")
    plt.legend(loc="center right", fontsize=9)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    out = ROOT / "learning_curve.png"
    plt.savefig(out, dpi=130)
    print("wrote", out)


def arm_comparison():
    truth = json.load(open(ROOT / "truth.json"))
    arms = [("cold", "no memory\n(cold)", "#d62728"),
            ("md", "plain .md\n(read-it-all)", "#ff7f0e"),
            ("memory", "Gemmery\n(retrieved)", "#1f77b4")]
    labels, vals, colors = [], [], []
    for key, lab, col in arms:
        p = ROOT / f"answer_{key}.json"
        if not p.exists():
            continue
        txt = p.read_text().strip()
        if "```" in txt:
            txt = txt.split("```")[1].lstrip("json").strip()
        ans = json.loads(txt)
        acc = sum(ans.get(g) == truth[g] for g in truth) / len(truth)
        labels.append(lab); vals.append(acc); colors.append(col)

    plt.figure(figsize=(6.5, 4.5))
    bars = plt.bar(labels, vals, color=colors, width=0.6)
    plt.axhline(0.25, ls="--", c="gray", lw=1)
    plt.text(len(labels) - 0.5, 0.27, "chance", color="gray", fontsize=9, ha="right")
    for b, v in zip(bars, vals):
        plt.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.2f}",
                 ha="center", fontweight="bold")
    plt.ylim(0, 1.08)
    plt.ylabel(f"wolf-ID accuracy  (LLM focal, n={len(truth)} games)")
    plt.title("Does the memory backend matter? (matched compute)")
    plt.tight_layout()
    out = ROOT / "arm_comparison.png"
    plt.savefig(out, dpi=130)
    print("wrote", out)


if __name__ == "__main__":
    learning_curve()
    try:
        arm_comparison()
    except Exception as e:
        print("arm_comparison skipped:", e)
