"""Score the drift evaluation: cold vs md-append vs gemmery-revised-dossiers.

Reports overall accuracy, the two designed cells (real wolf HID its tell while
innocent P2 showed its new Seer habit — the stale trap; and P2-wolf-silent — the
new tell), and per-arm token spend if provided.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
truth = json.load(open(ROOT / "truth.json"))
GIDS = sorted(truth, key=lambda g: int(g[1:]))
# cells by construction in build.py spec:
HIDDEN_CELL = ["T0", "T1", "T3"]      # wolf hid; innocent P2 claimed Seer
P2_WOLF_CELL = ["T2", "T5"]           # P2 is the wolf (silent = new tell)
SHOWN_CELL = ["T4", "T7"]             # wolf showed its tell


def load(arm):
    p = ROOT / "out" / f"{arm}.json"
    if not p.exists():
        return {}
    t = p.read_text().strip()
    if "```" in t:
        t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)


ans = {a: load(a) for a in ("cold", "md", "gemmery")}
print(f"{'game':>4} {'truth':>6} {'cold':>6} {'md':>6} {'gemmery':>8}")
print("-" * 36)
acc = {a: 0 for a in ans}
for g in GIDS:
    row = []
    for a in ("cold", "md", "gemmery"):
        p = ans[a].get(g, "?"); ok = p == truth[g]; acc[a] += ok
        row.append(f"{p}{'✓' if ok else '✗'}")
    print(f"{g:>4} {truth[g]:>6} {row[0]:>6} {row[1]:>6} {row[2]:>8}")
print("-" * 36)
n = len(GIDS)
for a in ("cold", "md", "gemmery"):
    print(f"  {a:8s}: {acc[a]}/{n} = {acc[a]/n:.2f}")

print("\nby cell (the designed traps):")
for name, cell in [("stale-trap (wolf hid, P2 claimed Seer)", HIDDEN_CELL),
                   ("P2-wolf (new silent tell)", P2_WOLF_CELL),
                   ("wolf showed tell", SHOWN_CELL)]:
    line = "  ".join(f"{a}={sum(ans[a].get(g) == truth[g] for g in cell)}/{len(cell)}"
                     for a in ("cold", "md", "gemmery"))
    print(f"  {name:42s} {line}")

json.dump({a: acc[a] / n for a in ans}, open(ROOT / "result.json", "w"), indent=1)
