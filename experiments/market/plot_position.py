"""Cost-sweep figure: simulation's net gain = friction-proofing."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent
R = json.load(open(ROOT / "position_results.json"))
costs = sorted(int(k) for k in R)
arms = [("naive", "#d62728", "naive signal-chaser (no lookahead)"),
        ("greedy", "#ff7f0e", "greedy (1-step cost-aware)"),
        ("planner", "#1f77b4", "planner (H=10 simulation over fitted MDP)")]
fig, ax = plt.subplots(1, 2, figsize=(13, 4.7))
for a, col, lab in arms:
    ax[0].plot(costs, [R[str(c)][a]["total_bps"]/1e4 for c in costs], "-o", lw=2.4, color=col, label=lab)
ax[0].set_xlabel("transaction cost (bps per unit turnover)")
ax[0].set_ylabel("cumulative net P&L (% points, summed over 85 books, 14yr)")
ax[0].set_title("Simulation's net gain = friction-proofing:\nthe planner keeps the whole edge as costs rise "
                "(2,251→2,291); myopic arms collapse")
ax[0].legend(fontsize=8); ax[0].grid(alpha=0.25)
for a, col, lab in arms:
    ax[1].plot(costs, [R[str(c)][a]["turnover"]/1000 for c in costs], "-o", lw=2.4, color=col, label=lab)
ax[1].set_yscale("log")
ax[1].set_xlabel("transaction cost (bps)")
ax[1].set_ylabel("total turnover (K position changes, log)")
ax[1].set_title("How: the planner trades 15.9K→1.1K as friction rises\n(the no-trade band emerges from "
                "lookahead); naive cannot adapt (62K always)")
ax[1].legend(fontsize=8); ax[1].grid(alpha=0.25, which="both")
plt.tight_layout(); plt.savefig(ROOT / "position_results.png", dpi=130)
print("wrote", ROOT / "position_results.png")
