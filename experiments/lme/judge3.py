"""v2 judge prompts + scoring (reader3_/judge3_ files), with v1 comparison."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
meta = {m["qid"]: m for m in json.load(open(ROOT / "meta.json"))}

def clean(t):
    t = t.strip()
    if "```" in t:
        t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)

def build_judge():
    ans = {}
    for b in range(6):
        p = ROOT / "out" / f"reader3_{b}.json"
        if p.exists():
            ans.update(clean(p.read_text()))
    print(f"answers: {len(ans)}/60  missing: {[q for q in meta if q not in ans]}")
    ids = sorted(meta)
    HDR = ("You are grading a memory system's answers. For each item decide if "
           "the MODEL ANSWER is correct given the GOLD answer: semantically "
           "equivalent or containing the gold fact = correct. For items whose id "
           "ends in _abs, the gold behavior is abstaining: correct iff the model "
           "declined to answer (e.g. \"I don't know\"). A \"(missing)\" model "
           "answer = false. Return ONLY JSON mapping id to true/false.\n\n")
    for half in (0, 1):
        body = HDR
        for qid in ids[half*30:(half+1)*30]:
            m = meta[qid]
            body += (f"=== {qid} ===\nquestion: {m['question']}\n"
                     f"gold: {m['answer']}\nmodel: {ans.get(qid,'(missing)')}\n\n")
        (ROOT / f"prompt_judge3_{half}.txt").write_text(body)
    print("judge2 prompts written")

def score():
    verd = {}
    for half in (0, 1):
        verd.update(clean((ROOT / "out" / f"judge3_{half}.json").read_text()))
    v1 = json.load(open(ROOT / "results.json"))
    by_type, overall, abst = {}, [0, 0], [0, 0]
    for qid, ok in verd.items():
        m = meta[qid]; t = m["type"]
        by_type.setdefault(t, [0, 0])
        by_type[t][0] += bool(ok); by_type[t][1] += 1
        overall[0] += bool(ok); overall[1] += 1
        if qid.endswith("_abs"):
            abst[0] += bool(ok); abst[1] += 1
    print(f"OVERALL v3: {overall[0]}/{overall[1]} = {overall[0]/overall[1]:.3f}"
          f"   (v1 was {v1['overall']:.3f})")
    for t, (c, n) in sorted(by_type.items()):
        print(f"  {t:28s} {c}/{n} = {c/n:.2f}   (v1 {v1['by_type'][t]:.2f})")
    print(f"  {'abstention (_abs)':28s} {abst[0]}/{abst[1]} = {abst[0]/abst[1]:.2f}"
          f"   (v1 {v1['abstention']:.2f})")
    json.dump({"overall": overall[0]/overall[1],
               "by_type": {t: round(c/n, 3) for t, (c, n) in by_type.items()},
               "abstention": abst[0]/abst[1], "n": overall[1],
               "verdicts": verd},
              open(ROOT / "results_v3.json", "w"), indent=1)

if __name__ == "__main__":
    (build_judge if sys.argv[1] == "judge" else score)()
