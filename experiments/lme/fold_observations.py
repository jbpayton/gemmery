"""Fold observer outputs into (a) ONE Gemmery store — users/<qid>/<topic>,
slug reuse = revise() so version chains are real git history — and
(b) v3 reader prompts: each question gets its user's WHOLE distilled memory
(no retrieval), topics with dated version chains, latest last.
"""
import json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))

def clean(t):
    t = t.strip()
    if "```" in t:
        t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)

def load_all():
    meta = json.load(open(ROOT / "meta.json"))
    obs, missing, bad = {}, [], []
    for m in meta:
        p = ROOT / "obs" / f"obs_{m['qid']}.json"
        if not p.exists():
            missing.append(m["qid"]); continue
        try:
            arr = clean(p.read_text())
            assert isinstance(arr, list) and all("obs" in o for o in arr)
            obs[m["qid"]] = arr
        except Exception as e:
            bad.append((m["qid"], str(e)[:60]))
    return meta, obs, missing, bad

def build_store(obs):
    from gemmery import Action, Gem, IndexKeys, Kind, KnowledgeBody, Provenance, GitStore
    if (ROOT / "store_v3").exists():
        shutil.rmtree(ROOT / "store_v3")
    st = GitStore(ROOT / "store_v3")
    n_cap = n_rev = 0
    for qid, arr in obs.items():
        seen = set()
        for o in arr:
            slug = re.sub(r"[^a-z0-9-]", "-", str(o.get("topic", "misc")).lower())[:60] or "misc"
            path = f"users/{qid}/{slug}"
            gem = Gem(kind=Kind.knowledge,
                      provenance=Provenance("observer", f"user-{qid}"),
                      body=KnowledgeBody(
                          action=Action("observe", {"date": o.get("date", "?")}),
                          reasoning=f"[{o.get('date','?')}] {o['obs']}",
                          belief=o["obs"][:120]),
                      index_keys=IndexKeys(action_type="observation", domain=[qid]))
            if path in seen:
                st.revise(gem, path); n_rev += 1
            else:
                st.capture(gem, path=path); seen.add(path); n_cap += 1
    return st, n_cap, n_rev

def emit_prompts(meta, obs):
    HDR = ("You answer questions about a user from their DISTILLED MEMORY: "
           "dated atomic observations grouped by topic. When a topic has "
           "several dated versions, they are listed oldest->newest; the "
           "LATEST entry BEFORE the question date is the current truth. "
           "For EACH question: think briefly step by step (quote observations "
           "and dates, do date arithmetic carefully), then decide. If the "
           "memory does not contain the answer, the answer is exactly "
           "\"I don't know\". After all questions, output ONE JSON object "
           "mapping question id to concise answer string.\n\n")
    ids = [m["qid"] for m in meta]
    toks = []
    for b in range(6):
        body = HDR
        for qid in ids[b*10:(b+1)*10]:
            m = next(x for x in meta if x["qid"] == qid)
            groups = {}
            for o in obs.get(qid, []):
                groups.setdefault(str(o.get("topic", "misc")), []).append(o)
            mem = []
            for topic, items in groups.items():
                items.sort(key=lambda o: str(o.get("date", "")))
                mem.append(f"{topic}:")
                mem += [f"  [{o.get('date','?')}] {o['obs']}" for o in items]
            block = "\n".join(mem)
            toks.append(len(block) // 4)
            body += (f"=== {qid} ===\nquestion date: {m['date']}\n"
                     f"question: {m['question']}\nmemory:\n{block}\n\n")
        (ROOT / f"prompt_reader3_{b}.txt").write_text(body)
    print(f"reader3 prompts KB: "
          f"{[(ROOT / f'prompt_reader3_{b}.txt').stat().st_size // 1024 for b in range(6)]}")
    print(f"distilled memory tokens/question ~ min/med/max: "
          f"{min(toks)}/{sorted(toks)[len(toks)//2]}/{max(toks)}  "
          f"(haystack ~115K -> compression ~{115000 // max(1, sorted(toks)[len(toks)//2])}x)")

if __name__ == "__main__":
    meta, obs, missing, bad = load_all()
    print(f"observations loaded: {len(obs)}/60  missing: {missing}  bad: {bad}")
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        sys.exit(0)
    st, n_cap, n_rev = build_store(obs)
    print(f"store_v3: {n_cap} topics captured, {n_rev} revisions "
          f"(slug reuse -> git history)")
    emit_prompts(meta, obs)
