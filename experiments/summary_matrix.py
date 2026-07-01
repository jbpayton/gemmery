"""Capstone: every memory approach vs every query type, one matrix.

Numbers are the measured accuracies from the experiments in this folder:
  - small memory (fits in context)     : werewolf (cold vs any memory)
  - rare existence                     : scale/alibi (scale_demo + vector_demo)
  - exact aggregate over a dense set    : scale/vector_demo (who-was-Gnosia-most)
  - complex noisy behavioral rule       : complex_rules/rules_demo
The Gemmery column = best of {vector, structured} per row, since it has both
layers over one DAG and can use whichever the query needs.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent

approaches = ["no\nmemory", "flat file\n(read/grep)", "vector\n(embeddings)",
              "structured\n(columnar)", "Gemmery\n(both layers)"]
rows = [
    "small memory\n(fits in context)",
    "rare existence\n('did X ever happen?')",
    "exact aggregate\n('who most / how often?')",
    "complex noisy rule\n('what will they do here?')",
]
# measured accuracies (see each experiment's RESULTS.md); Gemmery = max(vector,structured)
data = np.array([
    [0.36, 1.00, 1.00, 1.00, 1.00],
    [0.45, 0.53, 1.00, 1.00, 1.00],
    [0.50, 0.43, 0.57, 1.00, 1.00],
    [0.50, 0.50, 0.78, 0.61, 0.78],
])

fig, ax = plt.subplots(figsize=(9.5, 5.2))
im = ax.imshow(data, cmap="RdYlGn", vmin=0.35, vmax=1.0, aspect="auto")
ax.set_xticks(range(len(approaches)), approaches, fontsize=9)
ax.set_yticks(range(len(rows)), rows, fontsize=9)
for i in range(len(rows)):
    for j in range(len(approaches)):
        ax.text(j, i, f"{data[i, j]:.2f}", ha="center", va="center",
                fontsize=11, fontweight="bold",
                color="black" if data[i, j] > 0.55 else "white")
# outline the Gemmery column
ax.add_patch(plt.Rectangle((3.5, -0.5), 1, len(rows), fill=False, edgecolor="#1f3fff", lw=2.5))
ax.set_title("Where each memory approach wins — accuracy by query type\n"
             "(no single-tool substrate is high on every row; the two-layer store is)",
             fontsize=11)
cb = fig.colorbar(im, ax=ax, shrink=0.8)
cb.set_label("task accuracy")
plt.tight_layout()
out = ROOT / "summary_matrix.png"
plt.savefig(out, dpi=130)
print("wrote", out)
