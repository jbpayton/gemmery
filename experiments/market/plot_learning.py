"""Learning over time on real markets: rate vs accumulation."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).parent
d = json.load(open(ROOT / "learning_curve.json"))
ms, gem, flat = d["months"], d["mcc"]["gem"], d["mcc"]["flat"]
def roll3(x): return [np.mean(x[max(0,i-2):i+1]) for i in range(len(x))]

fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
ax[0].plot(roll3(gem), lw=2.4, color="#1f77b4", label="credit dossiers (decayed)")
ax[0].plot(roll3(flat), lw=2.0, color="#ff7f0e", label="flat recency log")
ax[0].axhline(0, color="gray", lw=1)
ax[0].fill_between(range(len(ms)), roll3(gem), 0, alpha=0.15, color="#1f77b4")
ax[0].set_xticks(range(0, len(ms), 3), ms[::3], rotation=45, fontsize=7)
ax[0].set_ylabel("monthly MCC (3-mo rolling)")
ax[0].set_title("Rate of edge: dossiers lock on within ~2 months, then MAINTAIN\n"
                "through regimes (halves: +0.043 / +0.045). Flat never learns (mean −0.03)")
ax[0].legend(fontsize=8); ax[0].grid(alpha=0.25)

dates = [x[0] for x in d["conf_cum"]]; cum = [x[1] for x in d["conf_cum"]]
ax[1].plot(range(len(cum)), cum, lw=2.4, color="#2ca02c")
step = max(1, len(dates)//8)
ax[1].set_xticks(range(0, len(dates), step), [dates[i][:7] for i in range(0, len(dates), step)],
                 rotation=45, fontsize=7)
i_dip = int(np.argmax([c - min(cum[j:]) for j, c in enumerate(cum[:len(cum)//2])]))
ax[1].annotate("regime dip (late 2014):\ndrawdown, then decay prunes\nand the slope recovers",
               (len(cum)*0.42, 120), fontsize=8)
ax[1].set_ylabel("cumulative correct − wrong (confident calls, τ=0.02)")
ax[1].set_title("Accumulation of edge: 0 → +469 over 2 years,\n"
                "slope ~3× steeper in year 2 as shrinkage releases matured signals")
ax[1].grid(alpha=0.25)
plt.tight_layout(); plt.savefig(ROOT / "learning_over_time.png", dpi=130)
print("wrote", ROOT / "learning_over_time.png")
