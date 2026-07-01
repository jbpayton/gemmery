"""Score the complex-rule in-context induction confirmation."""
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
    return {k: int(v) for k, v in json.loads(t).items()}


ans = {a: load(a) for a in ("cold", "md", "gemmery")}
n = len(truth)
acc = {}
for a in ("cold", "md", "gemmery"):
    acc[a] = sum(ans[a].get(g) == truth[g] for g in truth) / n
print(f"predict a complex noisy rule (Bayes ceiling ~0.85), n={n}:")
print(f"  cold (no examples):            {acc['cold']:.2f}")
print(f"  md   (40 RANDOM examples):     {acc['md']:.2f}")
print(f"  gemmery (40 SIMILAR examples): {acc['gemmery']:.2f}")
json.dump(acc, open(ROOT / "llm_result.json", "w"), indent=1)
