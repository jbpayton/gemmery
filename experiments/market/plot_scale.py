"""Scale-up figure: per-era replication + 14-year accumulation."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).parent
R = json.load(open(ROOT / "scale_results.json"))
ys = R["years"]
fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.8))
x = np.arange(len(ys))
ax[0].bar(x - 0.22, [R["flat"][y] for y in ys], 0.42, color="#ff7f0e", label="flat recency log")
ax[0].bar(x + 0.22, [R["gem_decay"][y] for y in ys], 0.42, color="#1f77b4", label="credit dossiers (decayed)")
ax[0].plot(x, [R["gem_sel"][y][0] for y in ys], "k^--", ms=5, lw=1, label="dossiers, selective (τ=0.02)")
ax[0].axhline(0, color="gray", lw=1)
ax[0].set_xticks(x, ys, rotation=45, fontsize=8)
ax[0].set_ylabel("MCC (walk-forward, per year)")
ax[0].set_title("Replication across 14 years / 6 regimes (85 NASDAQ stocks, 184,767 episodes):\n"
                "dossiers positive 13/14 years (sign test p≈0.0009); flat negative most years")
ax[0].legend(fontsize=8); ax[0].grid(axis="y", alpha=0.25)

dates = [c[0] for c in R["conf_cum"]]; cum = [c[1] for c in R["conf_cum"]]
ax[1].plot(range(len(cum)), cum, lw=2.2, color="#2ca02c")
step = max(1, len(dates)//10)
ax[1].set_xticks(range(0, len(dates), step), [dates[i][:4] for i in range(0, len(dates), step)], fontsize=8)
ax[1].set_ylabel("cumulative correct − wrong (confident calls)")
ax[1].set_title("14 years of accumulated edge over a news corpus of ~280M tokens\n"
                "(≈1,400× a 200K context window — no reader could hold this; the dossiers aggregate it)")
ax[1].grid(alpha=0.25)
plt.tight_layout(); plt.savefig(ROOT / "scale_results.png", dpi=130)
print("wrote", ROOT / "scale_results.png")
