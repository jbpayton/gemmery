"""Score the scaled Gnosia experiment: selective (Gemmery) vs dump-all (.md) vs cold.

Correct = the named player is actually one of the game's 2 Gnosia (chance 2/8=0.25).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
truth = json.load(open(ROOT / "truth.json"))
OUT = ROOT / "out"
GIDS = sorted(truth, key=lambda g: int(g[1:]))


def parse(txt):
    txt = txt.strip()
    if "```" in txt:
        txt = txt.split("```")[1].lstrip("json").strip()
    return json.loads(txt)


def picks(arm):
    """Return {gid: pick}. Per-game files (gemmery/md) or one batched file (cold)."""
    out = {}
    batched = OUT / f"{arm}.json"
    if batched.exists():
        try:
            out.update(parse(batched.read_text()))
        except Exception:
            pass
    for g in GIDS:
        f = OUT / f"{arm}_{g}.json"
        if f.exists():
            try:
                out.update(parse(f.read_text()))
            except Exception:
                pass
    return out


rows = {arm: picks(arm) for arm in ("cold", "md", "gemmery")}
print(f"{'game':>5}  {'gnosia (either ok)':<22} {'cold':>5} {'md':>5} {'gemmery':>8}")
print("-" * 56)
acc = {a: 0 for a in rows}
n = len(GIDS)
for g in GIDS:
    t = truth[g]
    cells = []
    for arm in ("cold", "md", "gemmery"):
        p = rows[arm].get(g, "?")
        ok = p in t
        acc[arm] += ok
        cells.append(f"{p}{'✓' if ok else '✗'}")
    print(f"{g:>5}  {','.join(t):<22} {cells[0]:>5} {cells[1]:>5} {cells[2]:>8}")

print("-" * 56)
print("chance = 0.25")
for arm in ("cold", "md", "gemmery"):
    print(f"  {arm:8s}: {acc[arm]}/{n} = {acc[arm]/n:.2f}")
print(f"  selective-retrieval effect (gemmery - md): {(acc['gemmery']-acc['md'])/n:+.2f}")

json.dump({a: acc[a] / n for a in rows}, open(ROOT / "result.json", "w"), indent=1)
