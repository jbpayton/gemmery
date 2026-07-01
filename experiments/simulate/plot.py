"""Graph: expected reward vs planning horizon, for good / under-trust / over-trust
memory models. Run: .venv/bin/python experiments/simulate/plot.py"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from simulate_demo import sweep, HORIZONS, START, L  # noqa: E402

good = sweep(0.9, 0.9)
under = sweep(0.52, 0.9)
over = sweep(0.9, 0.5)
need = START + L + 1

plt.figure(figsize=(8.4, 4.9))
plt.plot(HORIZONS, [good[h] for h in HORIZONS], "-o", lw=2.4, color="#1f77b4",
         label="good model of the source (q≈truth)")
plt.plot(HORIZONS, [under[h] for h in HORIZONS], "-o", lw=2.2, color="#7f7f7f",
         label="under-trust (model thinks source ≈ useless)")
plt.plot(HORIZONS, [over[h] for h in HORIZONS], "-o", lw=2.2, color="#d62728",
         label="over-trust (model wrong: source is a coin)")
plt.axhline(0, ls="--", c="gray", lw=1)
plt.text(4.1, 0.4, "acting blind ≈ 0", fontsize=8, color="gray")
plt.axvline(need, ls=":", c="black", lw=1.8)
plt.text(need + 0.15, -6, f"need ~{need} steps of\nlookahead to 'see'\nthe detour pay off",
         fontsize=8)
plt.xlabel("planning horizon (how many steps ahead you simulate)")
plt.ylabel("expected reward")
plt.title("Adding a 'simulate' step: lookahead only pays past a horizon threshold,\n"
          "and only if the memory-model of the source is right (else it hurts)")
plt.legend(fontsize=9, loc="center right")
plt.grid(alpha=0.25)
plt.tight_layout()
out = ROOT / "simulate_horizon.png"
plt.savefig(out, dpi=130)
print("wrote", out)
