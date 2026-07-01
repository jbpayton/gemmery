"""Graph: as the situation gets more complex (more features), the EXACT
conditional lookup collapses toward chance while SIMILARITY retrieval holds.
Run: .venv/bin/python experiments/complex_rules/plot.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from rules_demo import evaluate  # noqa: E402

NFS = [4, 6, 8, 10, 12, 14, 16]
rows = {k: [] for k in ["exact_cell_conditional", "knn_similarity",
                        "base_rate_marginal", "bayes_ceiling"]}
occ = []
for nf in NFS:
    res = [evaluate(s, nf) for s in range(6)]
    for k in rows:
        rows[k].append(np.mean([r[k] for r in res]))
    occ.append(np.mean([r["avg_exact_cell_samples"] for r in res]))

plt.figure(figsize=(8.3, 4.8))
plt.plot(NFS, rows["knn_similarity"], "-o", lw=2.3, color="#1f77b4",
         label="similarity retrieval (kNN over situations)")
plt.plot(NFS, rows["exact_cell_conditional"], "-o", lw=2.3, color="#2ca02c",
         label="exact conditional lookup (structured filter)")
plt.plot(NFS, rows["base_rate_marginal"], "--", lw=1.6, color="#7f7f7f",
         label="marginal base-rate (ignores situation)")
plt.plot(NFS, rows["bayes_ceiling"], ":", lw=1.8, color="black", label="Bayes ceiling (the rule)")
plt.ylim(0.4, 0.9)
plt.xlabel("number of situational features (complexity of the behavioral rule)")
plt.ylabel("accuracy predicting the person's next move")
plt.title("Complex noisy rules flip the winner: SIMILARITY generalizes,\n"
          "EXACT conditional lookup starves as situations get sparse")
plt.legend(fontsize=9, loc="center left")
plt.grid(alpha=0.25)
# annotate cell occupancy
for nf, o in zip(NFS, occ):
    if nf in (8, 12, 16):
        plt.annotate(f"{o:.1f} samples\nin exact cell", (nf, 0.61),
                     fontsize=7, ha="center", color="#2ca02c")
plt.tight_layout()
out = ROOT / "complexity_flip.png"
plt.savefig(out, dpi=130)
print("wrote", out)
