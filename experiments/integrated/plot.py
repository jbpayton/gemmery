"""Graph: git-served vs markdown-served vs no-memory planning, and how the gap
amplifies with plan length. Run: .venv/bin/python experiments/integrated/plot.py"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from integrated_demo import run, plan_reward  # noqa: E402

prof, current, gm, mm, _ = run()
Ts = [1, 2, 3, 4, 5, 6, 7, 8]
none = [0.5 ** T for T in Ts]
md = [plan_reward(mm, current, T) for T in Ts]
git = [plan_reward(gm, current, T) for T in Ts]

plt.figure(figsize=(8.4, 4.9))
plt.plot(Ts, git, "-o", lw=2.4, color="#1f77b4", label="git-served (recency-exact model)")
plt.plot(Ts, none, "--", lw=1.8, color="#7f7f7f", label="no memory (act blind)")
plt.plot(Ts, md, "-o", lw=2.2, color="#d62728",
         label="markdown-served (stale model: over-trusts a fallen advisor)")
plt.yscale("log")
plt.xlabel("plan length T (steps of reliance on the chosen advisor)")
plt.ylabel("P(plan succeeds)  [log scale]")
plt.title("git memory serving a plan vs vanilla vs none\n"
          "a miscalibrated (markdown) model plans BELOW no-memory; the gap grows with horizon")
plt.legend(fontsize=9, loc="lower left")
plt.grid(alpha=0.25, which="both")
plt.tight_layout()
out = ROOT / "integrated_plan.png"
plt.savefig(out, dpi=130)
print("wrote", out)
