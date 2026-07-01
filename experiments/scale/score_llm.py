"""Score the real-agent confirmation of the beyond-context scale demo."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
truth = json.load(open(ROOT / "llm_truth.json"))
OUT = ROOT / "out"


def load(arm):
    p = OUT / f"{arm}.json"
    if not p.exists():
        return {}
    t = p.read_text().strip()
    if "```" in t:
        t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)


print(f"{'game':>5}  {'gnosia':>6}  {'cold':>6} {'md':>6} {'gemmery':>8}")
print("-" * 42)
acc = {a: 0 for a in ("cold", "md", "gemmery")}
ans = {a: load(a) for a in acc}
n = len(truth)
for g in sorted(truth):
    row = []
    for a in ("cold", "md", "gemmery"):
        p = ans[a].get(g, "?"); ok = p == truth[g]; acc[a] += ok
        row.append(f"{p}{'✓' if ok else '✗'}")
    print(f"{g:>5}  {truth[g]:>6}  {row[0]:>6} {row[1]:>6} {row[2]:>8}")
print("-" * 42)
for a in ("cold", "md", "gemmery"):
    print(f"  {a:8s}: {acc[a]}/{n} = {acc[a]/n:.2f}")
json.dump({a: acc[a]/n for a in acc}, open(ROOT / "llm_result.json", "w"), indent=1)
