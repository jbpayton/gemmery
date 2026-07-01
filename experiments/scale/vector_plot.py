"""Grouped-bar graph: vector RAG ties the index on retrieval, but only the
structured index does exact aggregation. Numbers from vector_demo.py."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent

# measured in vector_demo.py (200K records, real MiniLM embeddings)
groups = ["rare EXISTENCE\n('has P ever held R?')", "exact AGGREGATE\n('who was Gnosia most?')"]
methods = [("read-what-fits (flat file)", [0.53, 0.43], "#d62728"),
           ("vector RAG (embeddings)", [1.00, 0.57], "#ff7f0e"),
           ("Gemmery columnar index", [1.00, 1.00], "#1f77b4")]

x = np.arange(len(groups)); w = 0.26
plt.figure(figsize=(8.5, 4.8))
for i, (lab, vals, col) in enumerate(methods):
    bars = plt.bar(x + (i - 1) * w, vals, w, label=lab, color=col)
    for b, v in zip(bars, vals):
        plt.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.2f}",
                 ha="center", fontsize=9, fontweight="bold")
plt.axhline(0.5, ls=":", c="gray", lw=1)
plt.xticks(x, groups)
plt.ylim(0, 1.12)
plt.ylabel("accuracy")
plt.title("The real boundary: vector RAG matches the index on retrieval,\n"
          "but only a structured index does exact aggregation")
plt.legend(loc="lower left", fontsize=9)
plt.grid(axis="y", alpha=0.25)
plt.tight_layout()
out = ROOT / "vector_vs_index.png"
plt.savefig(out, dpi=130)
print("wrote", out)
