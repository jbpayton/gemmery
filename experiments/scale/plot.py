"""Graph: accuracy vs how much of the history a reader can hold.
Run: .venv/bin/python experiments/scale/plot.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scale_demo import run_deterministic  # noqa: E402

_, _, _, _, res = run_deterministic()
fracs = [f * 100 for f, _ in res["curve"]]
accs = [a for _, a in res["curve"]]
ctx_frac = res["window_fraction_that_fits"] * 100

plt.figure(figsize=(8.2, 4.8))
plt.plot(fracs, accs, "-o", lw=2.2, color="#ff7f0e",
         label="markdown: read as much as fits, then decide")
plt.axhline(res["acc_index_exact"], ls="-", lw=2.2, color="#1f77b4",
            label="Gemmery index: exact query (context-independent)")
plt.axhline(res["acc_cold_random"], ls="--", lw=1.5, color="#d62728", label="no memory (cold)")
plt.axvline(ctx_frac, ls=":", lw=2, color="black")
plt.text(ctx_frac * 1.1, 0.3, f"a context window\nholds ~{ctx_frac:.1f}% of\nthis history",
         fontsize=9)
plt.xscale("log")
plt.ylim(0, 1.05)
plt.xlabel("% of career history the reader can hold in context (log scale)")
plt.ylabel(f"accuracy: catch the lying Gnosia (n={len(res['curve']) and 40})")
mb = res["total_chars"] / 1e6
plt.title(f"When memory ({res['total_tokens_est']//1000}K tokens ≈ {mb:.0f} MB) "
          f"dwarfs the context window,\nreading fails and the index is the only "
          f"thing that works")
plt.legend(loc="center left", fontsize=9)
plt.grid(alpha=0.25, which="both")
plt.tight_layout()
out = ROOT / "context_wall.png"
plt.savefig(out, dpi=130)
print("wrote", out)
