"""Bar chart: drift evaluation, overall + by designed cell."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
cells = ["overall\n(n=8)", "wolf showed\ntell (n=2)", "stale trap:\nwolf hid (n=3)", "P2-wolf, new\nsilent tell (n=2)"]
data = {  # from score.py
    "cold": [0.25, 0.0, 0.0, 1.0],
    "md (append, read-all 17.7KB)": [0.50, 1.0, 1/3, 0.0],
    "gemmery (revised dossiers 2.9KB)": [0.50, 1.0, 1/3, 0.0],
}
colors = ["#d62728", "#ff7f0e", "#1f77b4"]
x = np.arange(len(cells)); w = 0.26
plt.figure(figsize=(9, 4.8))
for i, (lab, vals) in enumerate(data.items()):
    b = plt.bar(x + (i - 1) * w, vals, w, label=lab, color=colors[i])
    for bb, v in zip(b, vals):
        plt.text(bb.get_x() + bb.get_width()/2, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
plt.xticks(x, cells, fontsize=9)
plt.ylim(0, 1.15)
plt.ylabel("wolf-ID accuracy")
plt.title("Behavioral drift: append-only notes vs revised dossiers (LLM focals)\n"
          "another accuracy tie — revision is a write-time compression, not an accuracy edge (at this scale)")
plt.legend(fontsize=8, loc="upper center")
plt.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig(ROOT / "drift_result.png", dpi=130)
print("wrote", ROOT / "drift_result.png")
