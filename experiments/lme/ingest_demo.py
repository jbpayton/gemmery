"""Ingest ONE sampled question's haystack into a real Gemmery store (artifact).

Every turn -> an observation gem at sessions/<date>/s<i>/<role>-t<j>; the
question's answer-evidence turns land where retrieval found them. Shows what a
LongMemEval memory looks like as a Gemmery filesystem.
"""
import json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
from gemmery import Action, Gem, IndexKeys, Kind, KnowledgeBody, Provenance, GitStore

DATA = ROOT.parents[1] / "data" / "lme"
d = json.load(open(DATA / "lme_s.json"))
meta = json.load(open(ROOT / "meta.json"))
# pick a knowledge-update question (revision-shaped) that we sampled
qid = next(m["qid"] for m in meta if m["type"] == "knowledge-update")
q = next(x for x in d if x["question_id"] == qid)

if (ROOT / "store").exists():
    shutil.rmtree(ROOT / "store")
st = GitStore(ROOT / "store")
n = 0
for si, (sess, sid, date) in enumerate(zip(
        q["haystack_sessions"], q["haystack_session_ids"], q["haystack_dates"])):
    day = date.split(" ")[0].replace("/", "-")
    for tj, t in enumerate(sess):
        txt = (t.get("content") or "").strip()
        if len(txt) < 15:
            continue
        gem = Gem(kind=Kind.knowledge,
                  provenance=Provenance("ingest", f"session-{sid}"),
                  body=KnowledgeBody(
                      action=Action("observe_turn", {"session": sid, "date": date}),
                      reasoning=txt[:1500],
                      belief=f"{t['role']} said this on {date}"),
                  index_keys=IndexKeys(action_type="turn", domain=[t["role"], day]))
        st.capture(gem, path=f"sessions/{day}/s{si}/{t['role']}-t{tj}")
        n += 1
print(f"question: {q['question']!r} (type {q['question_type']})")
print(f"gold: {q['answer']}  evidence sessions: {q['answer_session_ids']}")
print(f"ingested {n} turn-gems across {len(q['haystack_sessions'])} sessions")
print("days:", len(st.ls("sessions")))
