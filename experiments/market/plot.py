"""Market backtest figures: arms, signal-credit trajectories, abstention."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent
R = json.load(open(ROOT / "backtest_results.json"))
fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))

arms = ["none", "flat", "gem_all", "gem_decay"]
labels = ["no memory\n(prior)", "flat log\n(recency read)", "dossiers\n(all-history)", "dossiers\n(decayed)"]
mcc = [R["arms"][a]["mcc"] for a in arms]
colors = ["#d62728", "#ff7f0e", "#74a9cf", "#1f77b4"]
b = ax[0].bar(labels, mcc, color=colors, width=0.6)
for bb, v in zip(b, mcc):
    ax[0].text(bb.get_x() + bb.get_width()/2, v + 0.001, f"{v:+.3f}", ha="center", fontsize=9, fontweight="bold")
ax[0].axhline(0, color="gray", lw=1)
ax[0].axhline(0.081, ls="--", color="gray", lw=1)
ax[0].text(0.03, 0.083, "StockNet paper (neural, full coverage): 0.081", fontsize=7, color="gray")
ax[0].set_ylabel("MCC (test, walk-forward)"); ax[0].set_ylim(-0.01, 0.105)
ax[0].set_title("Credit-weighted dossiers find real signal;\nflat memory is useless-to-harmful")
ax[0].grid(axis="y", alpha=0.25)

show = ["mom1_up", "mom5_up", "big_drop_reversal", "tweets_bullish", "tweet_burst", "burst_bullish"]
cmap = {"mom1_up": "#999", "mom5_up": "#bbb", "big_drop_reversal": "#777",
        "tweets_bullish": "#2ca02c", "tweet_burst": "#e2b96f", "burst_bullish": "#1f77b4"}
for s in show:
    tr = R["traj"].get(s, [])
    if len(tr) < 3: continue
    xs = range(len(tr)); ys = [p for _, p, _ in tr]
    ax[1].plot(xs, ys, lw=2, color=cmap[s], label=s)
ax[1].axhline(0.507, ls="--", c="gray", lw=1)
ax[1].text(0.2, 0.509, "prior (0.507)", fontsize=7, color="gray")
tr0 = R["traj"]["mom1_up"]
ax[1].set_xticks(range(0, len(tr0), 4), [m for m, _, _ in tr0][::4], rotation=45, fontsize=7)
ax[1].set_ylabel("dossier p(up | signal fired)")
ax[1].set_title("Signal dossiers earning (and failing to earn) credit:\ntweet signals live, price momentum dead")
ax[1].legend(fontsize=7); ax[1].grid(alpha=0.25)

cov = [c for _, c, _, _ in R["abstention"]]
am = [m for _, _, _, m in R["abstention"]]
aa = [a for _, _, a, _ in R["abstention"]]
ax[2].plot([c*100 for c in cov], am, "-o", lw=2.2, color="#1f77b4", label="MCC")
ax2b = ax[2].twinx()
ax2b.plot([c*100 for c in cov], aa, "-s", lw=1.8, color="#2ca02c", label="accuracy")
ax2b.set_ylabel("accuracy", color="#2ca02c")
ax[2].set_xlabel("coverage % (predict only when confident)")
ax[2].set_ylabel("MCC", color="#1f77b4")
ax[2].set_title("Knowing when you know:\nselective prediction reaches MCC +0.10 @ 30% coverage")
ax[2].grid(alpha=0.25)
plt.tight_layout(); plt.savefig(ROOT / "market_results.png", dpi=130)
print("wrote", ROOT / "market_results.png")
