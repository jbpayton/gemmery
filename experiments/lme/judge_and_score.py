"""Build judge prompts from reader answers; score judged verdicts per type."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
meta = {m["qid"]: m for m in json.load(open(ROOT / "meta.json"))}

def load_answers():
    ans = {}
    for b in range(6):
        p = ROOT / "out" / f"reader_{b}.json"
        if p.exists():
            t = p.read_text().strip()
            if "```" in t:
                t = t.split("```")[1].lstrip("json").strip()
            ans.update(json.loads(t))
    return ans

def build_judge():
    ans = load_answers()
    print(f"answers collected: {len(ans)}/60")
    ids = sorted(meta)
    HDR = ("You are grading a memory system's answers. For each item decide if "
           "the MODEL ANSWER is correct given the GOLD answer: semantically "
           "equivalent or containing the gold fact = correct. For items whose id "
           "ends in _abs, the gold behavior is abstaining: correct iff the model "
           "declined to answer (e.g. \"I don't know\"). Return ONLY JSON mapping "
           "id to true/false.\n\n")
    for half in (0, 1):
        chunk = ids[half*30:(half+1)*30]
        body = HDR
        for qid in chunk:
            m = meta[qid]
            body += (f"=== {qid} ===\nquestion: {m['question']}\n"
                     f"gold: {m['answer']}\nmodel: {ans.get(qid,'(missing)')}\n\n")
        (ROOT / f"prompt_judge_{half}.txt").write_text(body)
    print("judge prompts written")

def score():
    verd = {}
    for half in (0, 1):
        t = (ROOT / "out" / f"judge_{half}.json").read_text().strip()
        if "```" in t:
            t = t.split("```")[1].lstrip("json").strip()
        verd.update(json.loads(t))
    by_type, overall = {}, [0, 0]
    abst = [0, 0]
    for qid, ok in verd.items():
        m = meta[qid]
        t = m["type"]
        by_type.setdefault(t, [0, 0])
        by_type[t][0] += bool(ok); by_type[t][1] += 1
        overall[0] += bool(ok); overall[1] += 1
        if qid.endswith("_abs"):
            abst[0] += bool(ok); abst[1] += 1
    print(f"\nOVERALL: {overall[0]}/{overall[1]} = {overall[0]/overall[1]:.3f}")
    for t, (c, n) in sorted(by_type.items()):
        print(f"  {t:28s} {c}/{n} = {c/n:.2f}")
    print(f"  {'abstention (_abs subset)':28s} {abst[0]}/{abst[1]} = "
          f"{abst[0]/max(1,abst[1]):.2f}")
    json.dump({"overall": overall[0]/overall[1],
               "by_type": {t: c/n for t, (c, n) in by_type.items()},
               "abstention": abst[0]/max(1, abst[1]),
               "n": overall[1]},
              open(ROOT / "results.json", "w"), indent=1)

if __name__ == "__main__":
    (build_judge if sys.argv[1] == "judge" else score)()
