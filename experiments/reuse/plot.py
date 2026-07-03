"""Learning curves: keeping alternate-reality branches + outcomes vs wiping."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
g = json.load(open(ROOT / "gambler_curves.json"))
c = json.load(open(ROOT / "curves.json"))
n = len(g["ev"]["fresh"])

def roll(x, w=4):
    return [np.mean(x[max(0, i - w + 1):i + 1]) for i in range(len(x))]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 4.6))
a1.plot(roll(g["ev"]["persistent"]), "-o", ms=3.5, lw=2.2, color="#1f77b4",
        label="PERSISTENT store (keeps branches + outcomes)")
a1.plot(roll(g["ev"]["fresh"]), "-o", ms=3.5, lw=2.2, color="#d62728",
        label="FRESH store (wiped between runs)")
a1.axhline(g["opt"], ls="--", c="gray", lw=1.2, label=f"optimal ({g['opt']:.3f})")
a1.axvline(g["resolved_at"], ls=":", c="#1f77b4", lw=1.6)
a1.annotate("ambiguity resolved:\n1st kept outcome kills the\nwrong hypothesis",
            (g["resolved_at"], 0.52), xytext=(4.5, 0.50), fontsize=8,
            color="#1f77b4", arrowprops=dict(arrowstyle="->", color="#1f77b4"))
a1.set_xlabel("episode (recurring situations)"); a1.set_ylabel("planning EV (rolling)")
a1.set_title("Committing planner: persistence converges after 1 episode;\nwiping stays wrong forever")
a1.legend(fontsize=8); a1.grid(alpha=0.25)

a2.plot(c["fresh"]["sims"], "-", lw=2.2, color="#d62728", label="fresh: re-simulate everything")
a2.plot(c["persistent"]["sims"], "-", lw=2.2, color="#1f77b4",
        label="persistent: kept branches reused")
a2.set_xlabel("episode"); a2.set_ylabel("cumulative rollout simulations")
a2.set_title("Compute: kept branches halve simulation work\n(cache serves recurring situations)")
a2.legend(fontsize=8); a2.grid(alpha=0.25)
plt.tight_layout(); plt.savefig(ROOT / "reuse_curves.png", dpi=130)
print("wrote", ROOT / "reuse_curves.png")
