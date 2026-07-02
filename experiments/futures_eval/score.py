"""Score the branch-in-reasoning A/B: EV of picks + optimal-pick rate."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
meta = json.load(open(ROOT / "meta.json"))
base = json.load(open(ROOT / "baselines.json"))
SIDS = sorted(meta, key=lambda s: int(s[1:]))


def load(arm):
    t = (ROOT / "out" / f"{arm}.json").read_text().strip()
    if "```" in t:
        t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)


arms = {a: load(a) for a in ("direct", "branch")}
print(f"{'scn':>4} {'trap':>5} {'myopic':>7} {'best':>5} | {'direct':>7} {'branch':>7}")
print("-" * 46)
stats = {a: {"ev": 0.0, "opt": 0, "trap_opt": 0, "myopic_picks": 0} for a in arms}
n_trap = sum(1 for s in SIDS if meta[s]["trap"])
for s in SIDS:
    m = meta[s]
    row = []
    for a in ("direct", "branch"):
        p = arms[a].get(s, "?")
        ev = m["evs"].get(p, 0.0)
        stats[a]["ev"] += ev / len(SIDS)
        opt = p == m["best"]
        stats[a]["opt"] += opt
        if m["trap"]:
            stats[a]["trap_opt"] += opt
            stats[a]["myopic_picks"] += (p == m["myopic"])
        row.append(f"{p}{'✓' if opt else ('m' if p == m['myopic'] else '✗')}")
    print(f"{s:>4} {str(m['trap']):>5} {m['myopic']:>7} {m['best']:>5} | "
          f"{row[0]:>7} {row[1]:>7}")
print("-" * 46)
print(f"policy EV:  random={base['random']:.3f}  argmax-belief={base['argmax_belief']:.3f}  "
      f"OPTIMAL={base['ev_optimal']:.3f}")
for a in ("direct", "branch"):
    st = stats[a]
    print(f"  {a:7s}: EV={st['ev']:.3f}  optimal-picks={st['opt']}/{len(SIDS)}  "
          f"trap-cell optimal={st['trap_opt']}/{n_trap}  fell-for-myopic={st['myopic_picks']}/{n_trap}")
json.dump({a: stats[a] for a in arms}, open(ROOT / "result.json", "w"), indent=1)
