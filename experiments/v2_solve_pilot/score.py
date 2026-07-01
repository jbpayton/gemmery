"""Score the v2 solve experiment: real Claude agents WITH vs WITHOUT the
transferable approach in context, graded by the live ScoredVerifiers."""
import json
from collections import defaultdict
from pathlib import Path

from gemmery.eval import build_tasks
from gemmery.eval.solver import _extract_code, grade

ROOT = Path(__file__).resolve().parent
tasks = {t.id: t for t in build_tasks()}
batches = json.load(open(ROOT / "batches.json"))


def read_solution(arm, batch, tid):
    p = ROOT / f"out_{batch}_{arm}" / f"{tid}.py"
    if not p.exists():
        return None
    return _extract_code(p.read_text())  # tolerate stray fences


rows = []
for batch, ids in batches.items():
    for tid in ids:
        t = tasks[tid]
        out = {}
        for arm in ("memory", "nomemory"):
            code = read_solution(arm, batch, tid)
            if code is None:
                out[arm] = (0.0, False, "MISSING")
            else:
                s, ok = grade(t.verifier, code)
                out[arm] = (s, ok, "")
        rows.append((tid, t.family, t.approach_id, out["memory"], out["nomemory"]))

print(f"{'task':14s} {'family':13s} {'mem':>6s} {'cold':>6s}  {'Δ':>6s}  flag")
print("-" * 60)
agg = defaultdict(lambda: [0.0, 0.0, 0])  # family -> [sum_mem, sum_cold, n]
tot = [0.0, 0.0, 0, 0, 0]  # sum_mem, sum_cold, n, succ_mem, succ_cold
for tid, fam, ap, (sm, okm, fm), (sc, okc, fc) in rows:
    d = sm - sc
    flag = "+" if d > 0.02 else ("-" if d < -0.02 else "=")
    note = (fm or fc)
    print(f"{tid:14s} {fam:13s} {sm:6.2f} {sc:6.2f}  {d:+6.2f}  {flag} {note}")
    agg[fam][0] += sm; agg[fam][1] += sc; agg[fam][2] += 1
    tot[0] += sm; tot[1] += sc; tot[2] += 1
    tot[3] += int(okm); tot[4] += int(okc)

print("-" * 60)
print("by family (mean score):")
for fam, (sm, sc, n) in sorted(agg.items()):
    print(f"  {fam:14s} mem={sm/n:.2f}  cold={sc/n:.2f}  Δ={(sm-sc)/n:+.2f}  (n={n})")

n = tot[2]
print("-" * 60)
print(f"OVERALL  mean score:   memory={tot[0]/n:.3f}  cold={tot[1]/n:.3f}  "
      f"Δ={ (tot[0]-tot[1])/n:+.3f}")
print(f"OVERALL  success@thr:  memory={tot[3]}/{n}={tot[3]/n:.2f}  "
      f"cold={tot[4]}/{n}={tot[4]/n:.2f}")

json.dump([{"task": r[0], "family": r[1], "approach": r[2],
            "score_memory": r[3][0], "success_memory": r[3][1],
            "score_cold": r[4][0], "success_cold": r[4][1]} for r in rows],
          open(ROOT / "scores.json", "w"), indent=1)
print("\nwrote scores.json")
