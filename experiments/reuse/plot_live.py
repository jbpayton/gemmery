"""Retention over steps + learning-while-playing, one figure."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
h = json.load(open(ROOT / "live_game.json"))
n = len(h["ev"]); DRIFT = 30
def roll(x, w=6): return [np.mean(x[max(0, i-w+1):i+1]) for i in range(len(x))]

fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
# 1: learning while playing
ax[0].plot(roll(h["ev"]), lw=2.4, color="#1f77b4", label="learning agent (retains everything)")
ax[0].plot(roll(h["ev_fresh"]), lw=2.0, color="#d62728", label="no retention (seeds only)")
ax[0].axhline(1.0, ls="--", c="gray", lw=1.2, label="oracle (knows the current rule)")
ax[0].axvline(DRIFT, ls=":", c="black", lw=1.8)
ax[0].text(DRIFT + 0.8, 0.955, "opponent CHANGES\nits rule", fontsize=8)
ax[0].set_ylim(0.93, 1.005); ax[0].set_xlabel("round"); ax[0].set_ylabel("fraction of optimal EV (rolling)")
ax[0].set_title("Learning while you play:\nlearn → drift dip → re-learn (and briefly,\nconfident-stale < hedging-ignorant)")
ax[0].legend(fontsize=7.5, loc="lower left"); ax[0].grid(alpha=0.25)
# 2: retention over steps
ax[1].plot(h["records"], lw=2.2, color="#2ca02c", label="records retained")
ax[1].plot(h["branches"], lw=2.2, color="#7b52ab", label="kept rollout branches")
ax[1].plot(np.cumsum(h["cache_hit"]), lw=2.2, color="#e2b96f", label="cumulative branch reuses")
ax[1].axvline(DRIFT, ls=":", c="black", lw=1.8)
import numpy as _np
_drop = int(_np.argmin(_np.diff(h["records"]))) + 1
ax[1].annotate(f"detection LAGS drift: refit purges 19 stale\nrecords at round {_drop}, EV snaps back",
               (_drop, h["records"][_drop]), xytext=(20, 5), fontsize=8,
               arrowprops=dict(arrowstyle="->"))
ax[1].set_xlabel("round"); ax[1].set_ylabel("count")
ax[1].set_title("Retention over steps: the store grows,\nis pruned at drift, and gets reused")
ax[1].legend(fontsize=7.5, loc="upper left"); ax[1].grid(alpha=0.25)
# 3: reuse rate + ambiguity
ax[2].plot(roll(h["cache_hit"], 8), lw=2.2, color="#e2b96f", label="branch reuse rate (rolling)")
ax2 = ax[2].twinx()
ax2.step(range(n), h["hyp"], where="post", lw=2.0, color="#1f77b4", alpha=0.8)
ax2.set_ylabel("surviving hypotheses", color="#1f77b4"); ax2.set_ylim(0.5, 4.5)
ax[2].axvline(DRIFT, ls=":", c="black", lw=1.8)
ax[2].set_ylim(0, 1.02); ax[2].set_xlabel("round"); ax[2].set_ylabel("reuse rate")
ax[2].set_title("Reuse climbs as situations recur;\nambiguity resolves in play (2→1)")
ax[2].legend(fontsize=7.5, loc="upper left"); ax[2].grid(alpha=0.25)
plt.tight_layout(); plt.savefig(ROOT / "live_game.png", dpi=130)
print("wrote", ROOT / "live_game.png")
