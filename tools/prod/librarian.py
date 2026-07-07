"""SessionEnd hook: the librarian. Two jobs, in order:

1. FOLD OUTCOMES (no LLM): match outcomes.jsonl entries against gems whose
   declared tests appear in the command; tag_outcome -> credit accrues.
2. DISTILL JUDGMENT (one cheap LLM call): hand the session transcript tail +
   the current dossier index to `claude -p`; apply its capture/revise ops.
   Selectivity is the point - empty ops are a fine answer. Dossiers hold
   rules/rationale/citations (file:line, commit sha), never fact dumps.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prod_store import get_store, dossiers, OUTCOMES, LOG, STORE_PATH

MODEL = os.environ.get("GEMMERY_LIBRARIAN_MODEL", "haiku")
TAIL = 30000

def log(msg):
    STORE_PATH.mkdir(exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M')}] {msg}\n")

def fold_outcomes(store):
    if not OUTCOMES.exists():
        return 0
    rows = [json.loads(l) for l in OUTCOMES.read_text().splitlines() if l.strip()]
    if not rows:
        return 0
    tagged, matched = 0, set()
    for path, sha, g in dossiers(store):
        declared = (g.action().args or {}).get("tests", []) if g.action() else []
        for t in declared:
            for ri, r in enumerate(rows):
                if t in r["command"]:
                    tid = f"{t[:40]}@{r['ts']}"
                    store.tag_outcome(sha, tid, ok=r["ok"])
                    store.attach_success(sha, tid, 1.0 if r["ok"] else 0.0)
                    store.attach_credit(sha, 0.1 if r["ok"] else -0.2)
                    tagged += 1; matched.add(ri)
    keep = [r for ri, r in enumerate(rows) if ri not in matched][-200:]
    OUTCOMES.write_text("".join(__import__("json").dumps(r) + "\n" for r in keep))
    return tagged

def transcript_tail(path):
    msgs = []
    try:
        for line in open(path):
            try:
                j = json.loads(line)
            except Exception:
                continue
            m = j.get("message") or {}
            role, content = m.get("role"), m.get("content")
            if role not in ("user", "assistant") or not content:
                continue
            if isinstance(content, str):
                msgs.append(f"{role}: {content}")
            else:
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        msgs.append(f"{role}: {b['text']}")
    except Exception as e:
        log(f"transcript parse failed: {e}")
    return "\n\n".join(msgs)[-TAIL:]

PROMPT = """You are the memory librarian for the gemmery repo. Below: the
current dossier index, then the tail of a working session that just ended.

Decide what (if anything) from this session is DURABLE JUDGMENT worth keeping
for future sessions: a rule with its why, a falsified assumption, a gotcha
with its precondition, a decision with its rationale. NOT facts restatable
from the code, NOT session narrative. Most sessions yield 0-2 items; empty
lists are a good answer. If the session contradicts an existing dossier,
REVISE it (same path) rather than adding a new one.

Each item's content must be: the rule/decision (1-2 sentences), WHY (the
evidence from this session), a falsifiable claim if possible, and citations
into the raw record (file paths, commit shas, experiment names). <=150 words.
Optionally declare "tests": substrings of pytest commands whose pass/fail
should credit or debit this dossier (e.g. "tests/test_torture.py").

Return ONLY JSON: {"capture": [{"path": "knowledge/<slug>", "content": "...",
"tests": ["..."]}], "revise": [{"path": "<existing path>", "content": "...",
"tests": ["..."]}]}

=== CURRENT DOSSIERS ===
%s

=== SESSION TAIL ===
%s
"""

def apply_ops(store, raw):
    from gemmery import Action, Gem, IndexKeys, Kind, KnowledgeBody, Provenance
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    ops = json.loads(m.group(0) if m else raw)
    n = 0
    existing = {p for p, _, _ in dossiers(store)}
    for verb in ("capture", "revise"):
        for item in ops.get(verb, []):
            path = item["path"]
            if not path.startswith("knowledge/"):
                path = "knowledge/" + path.split("/")[-1]
            gem = Gem(kind=Kind.knowledge,
                      provenance=Provenance("librarian", "session-end"),
                      body=KnowledgeBody(
                          action=Action("dossier", {"tests": item.get("tests", [])}),
                          reasoning=item["content"],
                          belief=item["content"][:120]),
                      index_keys=IndexKeys(action_type="dossier", domain=["gemmery-repo"]))
            if verb == "revise" or path in existing:
                store.revise(gem, path)
            else:
                store.capture(gem, path=path)
            n += 1
    return n

def main():
    try:
        h = json.load(sys.stdin)
    except Exception:
        h = {}
    tp = h.get("transcript_path") or (sys.argv[1] if len(sys.argv) > 1 else None)
    store = get_store()
    tagged = fold_outcomes(store)
    if not tp or not Path(tp).exists():
        log(f"outcomes tagged={tagged}; no transcript, done")
        return
    tail = transcript_tail(tp)
    if len(tail) < 500:
        log(f"outcomes tagged={tagged}; session too small, skipped")
        return
    idx = "\n".join(f"- [[{p}]] {g.body.belief[:90]}" for p, _, g in dossiers(store)) or "(none yet)"
    try:
        r = subprocess.run(["claude", "-p", PROMPT % (idx, tail), "--model", MODEL],
                           capture_output=True, text=True, timeout=180)
        n = apply_ops(store, r.stdout.strip())
        log(f"outcomes tagged={tagged}; librarian ops applied={n} (model={MODEL})")
    except Exception as e:
        log(f"outcomes tagged={tagged}; librarian failed: {e}")

if __name__ == "__main__":
    main()
