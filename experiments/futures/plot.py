"""Diagram: the forked futures — EV, inhabitant stance, selection, execution."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent
F = json.load(open(ROOT / "futures.json"))
def load(v):
    t = (ROOT / "out" / f"vote-{v}.json").read_text().strip()
    if "```" in t: t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)

fig, ax = plt.subplots(figsize=(12.5, 6.2)); ax.axis("off")
def box(x, y, t, c, w=3.3, h=1.05, fs=8.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06", fc=c, ec="black", lw=1.2))
    ax.text(x + w/2, y + h/2, t, ha="center", va="center", fontsize=fs)
def arr(x1, y1, x2, y2, s="-", c="black", lw=1.4):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=13, lw=lw, color=c, ls=s))

box(0.1, 3.9, "decision point (main)\nDay-1 vote\nbelief: P2=.87 P3=.06\nP1=.04 P4=.03", "#dfe7f5", w=2.6, h=1.3)
ys = {"P2": 6.3, "P1": 4.75, "P3": 3.2, "P4": 1.65}
stance_c = {"endorse": "#bfe3bf", "caution": "#fdeeba", "reject": "#f3c9c9"}
for v, y in ys.items():
    a = load(v)
    sim = ("wolf caught Day 1,\nno losses" if v == "P2"
           else "innocent lost + night freeze,\nthen Day-2 catch of P2")
    box(3.5, y, f"frontier/future/vote-{v}\nEV {F['ev'][v]:.2f}   sim: {sim}",
        "#eeeeee", w=4.0, fs=7.8)
    arr(2.7, 4.55, 3.5, y + 0.5)
    box(8.0, y, f"inhabitant: {a['stance'].upper()} ({a['confidence_0_1']})\n"
        f"credit {F['ev'][v]-F['ev']['P2']:+.2f}", stance_c[a["stance"]], w=2.6, h=0.95, fs=8)
    arr(7.5, y + 0.5, 8.0, y + 0.5, s=":")
box(11.0, 5.7, "SELECTED\nvote-P2 → main\nexecuted: wolf WAS P2\nWIN Day 1  ✓", "#9ecae1", w=1.9, h=1.6, fs=8)
arr(10.6, ys["P2"] + 0.5, 11.0, 6.4, s="--", c="#1f77b4", lw=2)
ax.text(3.6, 0.9, "each future is a REAL git branch: plan + simulated rollout + inhabitant's case, "
        "diffable against the others;\nthe roads not taken remain standing, credited by their EV gap",
        fontsize=8.5, color="#444")
ax.set_xlim(0, 13.2); ax.set_ylim(0.6, 7.8)
ax.set_title("Branching predictive realities: four candidate futures, explored blind, "
             "independently ranked, one selected and executed", fontsize=11)
plt.tight_layout(); plt.savefig(ROOT / "futures_dag.png", dpi=130)
print("wrote", ROOT / "futures_dag.png")
