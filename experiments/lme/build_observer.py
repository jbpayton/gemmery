"""v3 librarian arm — emit per-question haystack files + observer instructions.

The observer is QUESTION-BLIND (write-time memory cannot see the future):
it reads a user's full session history and distills dated, atomic
observations. Reused topic slugs across sessions = revisions (Gemmery
revise() semantics rendered mechanically at fold time).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[1] / "data" / "lme"
(ROOT / "obs").mkdir(exist_ok=True)

INSTR = """You are a memory librarian. Below is one user's complete chat
history with an assistant: many sessions, each stamped with its date. Distill
it into dated, atomic observations that would let someone answer ANY future
question about this user WITHOUT the transcripts. You do not know what will
be asked — be comprehensive but compress hard.

Rules:
- BE COMPREHENSIVE: 8-20 observations per session — one per DISTINCT FACT the
  session contains. Losing a fact is worse than writing one extra line. A
  future question may hinge on any specific detail: an item ordered, a dish
  cooked, a person met, an amount paid, a day something happened.
- Each observation atomic, <= 50 words. PRESERVE SPECIFICS exactly: names,
  numbers, counts, prices, durations, dates-mentioned-in-content, product/
  place/media/event titles, who was present.
- Record what the ASSISTANT recommended or explained (titles, names, steps)
  when the user asked for it — future questions ask "what did you suggest...".
- Record user preferences WITH their stated reason.
- Every observation gets the session's datetime.
- topic: a stable kebab-case slug for the fact's subject. CRITICAL: when a
  later session UPDATES an earlier fact (a count changes, a plan changes, a
  job/home/status changes), REUSE THE EXACT SAME topic slug so versions chain.
- Skip only pure pleasantries. When in doubt, KEEP IT.

Output: ONLY a JSON array, each element
{"topic": "slug", "date": "<session datetime>", "obs": "text"}.
"""

def main():
    meta = json.load(open(ROOT / "meta.json"))
    want = {m["qid"] for m in meta}
    d = [q for q in json.load(open(DATA / "lme_s.json"))
         if q["question_id"] in want]
    sizes = []
    for q in d:
        lines = [INSTR, "\n===== SESSION HISTORY =====\n"]
        for sess, date in zip(q["haystack_sessions"], q["haystack_dates"]):
            lines.append(f"\n--- session {date} ---")
            for t in sess:
                txt = (t.get("content") or "").strip()
                if len(txt) < 15:
                    continue
                lines.append(f"({t['role']}): {txt[:1500]}")
        p = ROOT / "obs" / f"haystack_{q['question_id']}.txt"
        p.write_text("\n".join(lines))
        sizes.append(p.stat().st_size // 1024)
    print(f"{len(d)} haystack files, KB min/med/max: "
          f"{min(sizes)}/{sorted(sizes)[len(sizes)//2]}/{max(sizes)}")

if __name__ == "__main__":
    main()
