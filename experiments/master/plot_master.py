"""THE MASTER MATRIX: every approach x every regime. Color = fraction of the
row's achievable headroom captured ((x-floor)/(ceiling-floor)); text = the
absolute measured value in that row's units. Grey = never measured."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
rows = json.load(open(ROOT / "master.json"))
COLS = ["none", "flat", "vector", "exact", "gemmery"]
COL_LABELS = ["no\nmemory", "flat file\n(read/grep)", "vector\n(similarity)",
              "structured\n(exact)", "Gemmery\n(full stack)"]

n = len(rows)
norm = np.full((n, len(COLS)), np.nan)
for i, r in enumerate(rows):
    lo, hi = r["floor"], r["ceil"]
    for j, c in enumerate(COLS):
        v = r["cells"].get(c)
        if v is not None and hi > lo:
            norm[i, j] = min(1.0, max(0.0, (v - lo) / (hi - lo)))

fig, ax = plt.subplots(figsize=(12.5, 0.62 * n + 3))
cmap = plt.cm.RdYlGn.copy()
cmap.set_bad("#d9d9d9")
im = ax.imshow(np.ma.masked_invalid(norm), cmap=cmap, vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(COLS)), COL_LABELS, fontsize=9)
ax.set_yticks(range(n),
              [f"{r['row']}\n[{r['unit']}]" for r in rows], fontsize=8)
for i, r in enumerate(rows):
    for j, c in enumerate(COLS):
        v = r["cells"].get(c)
        if v is None:
            ax.text(j, i, "—", ha="center", va="center", fontsize=10, color="#777")
        else:
            dark = not np.isnan(norm[i, j]) and 0.25 < norm[i, j] < 0.8
            ax.text(j, i, f"{v:g}", ha="center", va="center", fontsize=9.5,
                    fontweight="bold", color="black")
ax.add_patch(plt.Rectangle((3.5, -0.5), 1, n, fill=False, ec="#1f3fff", lw=2.5))
cb = fig.colorbar(im, ax=ax, shrink=0.75)
cb.set_label("fraction of achievable headroom captured (per row)")
ax.set_title("THE MASTER SIDE-BY-SIDE — every memory approach vs every task regime\n"
             "cell text = absolute measured value (row units); deterministic rows "
             "re-run live, LLM rows from recorded arms; '—' = not measured",
             fontsize=11)
notes = "  •  ".join(f"R{i}: {r['note']}" for i, r in enumerate(rows) if r.get("note"))
fig.text(0.02, 0.012, "notes — " + notes, fontsize=5.5, wrap=True)
plt.tight_layout(rect=(0, 0.045, 1, 1))
plt.savefig(ROOT / "master_matrix.png", dpi=130)
print("wrote", ROOT / "master_matrix.png")
