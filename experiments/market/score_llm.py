"""Score LLM arms vs mechanical dossier policy on the same 60 episodes."""
import json, math
from pathlib import Path
ROOT = Path(__file__).parent
truth = json.load(open(ROOT/"llm_truth.json"))
mech = json.load(open(ROOT/"llm_mech.json"))
EIDS = sorted(truth, key=lambda e: int(e[1:]))

def load(arm):
    t = (ROOT/f"out_llm_{arm}.json").read_text().strip()
    if "```" in t: t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)

def mcc_acc(pairs):
    tp=tn=fp=fn=0
    for p,l in pairs:
        if p and l: tp+=1
        elif p: fp+=1
        elif l: fn+=1
        else: tn+=1
    den = math.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
    return (tp+tn)/len(pairs), ((tp*tn-fp*fn)/den) if den else 0.0

arms = {a: load(a) for a in ("cold","mem")}
mech_pred = {f"E{i}": 1 if m["p_mech"]>=0.5 else 0 for i,m in enumerate(mech)}
rows = {}
rows["mechanical dossiers"] = [(mech_pred[e], truth[e]) for e in EIDS]
for a, lab in (("cold","LLM cold (features only)"),("mem","LLM + dossier memory")):
    rows[lab] = [(1 if arms[a].get(e)=="U" else 0, truth[e]) for e in EIDS]
print(f"n={len(EIDS)}, up-rate={sum(truth.values())/len(truth):.2f}\n")
for lab, pairs in rows.items():
    acc, mcc = mcc_acc(pairs)
    print(f"{lab:26s} acc={acc:.3f}  mcc={mcc:+.3f}")
# does the memory arm FOLLOW the dossiers?
agree_mech = sum((arms['mem'].get(e)=='U') == (mech_pred[e]==1) for e in EIDS)
agree_cold = sum(arms['mem'].get(e)==arms['cold'].get(e) for e in EIDS)
print(f"\nmemory-arm agreement: with mechanical dossiers {agree_mech}/60, "
      f"with its own cold twin {agree_cold}/60")
json.dump({lab: mcc_acc(p) for lab,p in rows.items()},
          open(ROOT/"llm_arm_results.json","w"), indent=1)
