"""LongMemEval (sampled): Gemmery's retrieval layer + dated-turn memory.

Stratified 60-question sample of longmemeval_s_cleaned. Mechanical ingestion:
every turn becomes a dated memory record; bulk MiniLM embeddings (the vector
layer, batch mode); top-k=15 turns retrieved per question with session dates.
Free metric before any LLM: oracle retrieval recall (evidence sessions known).
Emits 6 batched reader prompts (10 questions each).
"""
import json, random, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[1] / "data" / "lme"
K = 15

def sample_questions():
    d = json.load(open(DATA / "lme_s.json"))
    rng = random.Random(7)
    by_type = {}
    for q in d:
        by_type.setdefault(q["question_type"], []).append(q)
    quota = {"single-session-user": 8, "single-session-assistant": 7,
             "single-session-preference": 4, "multi-session": 16,
             "temporal-reasoning": 16, "knowledge-update": 9}
    sel = []
    for t, n in quota.items():
        pool = by_type[t]
        # ensure abstention representation: prefer including _abs ids
        absq = [q for q in pool if q["question_id"].endswith("_abs")]
        rng.shuffle(absq); rng.shuffle(pool)
        take = absq[: max(1, n // 8)] if absq else []
        rest = [q for q in pool if q not in take]
        sel += take + rest[: n - len(take)]
    rng.shuffle(sel)
    return sel

def main():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    sel = sample_questions()
    print(f"sampled {len(sel)} questions "
          f"({sum(1 for q in sel if q['question_id'].endswith('_abs'))} abstention)")

    meta, recall_hits = [], 0
    blocks = {}
    for qi, q in enumerate(sel):
        turns, owners = [], []
        for si, (sess, sid, date) in enumerate(zip(
                q["haystack_sessions"], q["haystack_session_ids"], q["haystack_dates"])):
            for t in sess:
                txt = (t.get("content") or "")[:700]
                if len(txt) < 15:
                    continue
                turns.append(f"[{date}] ({t['role']}): {txt}")
                owners.append(sid)
        emb = model.encode(turns, batch_size=1024, convert_to_numpy=True,
                           normalize_embeddings=True, show_progress_bar=False)
        qv = model.encode([q["question"]], normalize_embeddings=True)[0]
        top = np.argsort(-(emb @ qv))[:K]
        retrieved = [turns[i] for i in top]
        gold_sids = set(q["answer_session_ids"])
        hit = any(owners[i] in gold_sids for i in top)
        if not q["question_id"].endswith("_abs"):
            recall_hits += hit
        meta.append({"qid": q["question_id"], "type": q["question_type"],
                     "question": q["question"], "date": q["question_date"],
                     "answer": str(q["answer"]), "oracle_hit": bool(hit),
                     "n_turns": len(turns)})
        blocks[q["question_id"]] = (q, retrieved)
        if (qi + 1) % 10 == 0:
            print(f"  embedded {qi+1}/{len(sel)}")

    n_scored = sum(1 for m in meta if not m["qid"].endswith("_abs"))
    print(f"\noracle retrieval recall@{K} (non-abstention): "
          f"{recall_hits}/{n_scored} = {recall_hits/n_scored:.3f}")
    json.dump(meta, open(ROOT / "meta.json", "w"), indent=1)

    HDR = ("You are answering questions about a user from your MEMORY of past "
           "chat sessions. For each question you get the top retrieved memory "
           "snippets (each stamped with its session date). Rules: (1) answer "
           "concisely from the memory; (2) when information changed over time, "
           "prefer the entry LATEST before the question date; (3) if the memory "
           "does not contain the answer, reply exactly \"I don't know\". Return "
           "ONLY JSON mapping question id to answer string.\n\n")
    ids = [m["qid"] for m in meta]
    for b in range(6):
        chunk = ids[b*10:(b+1)*10]
        body = HDR
        for qid in chunk:
            q, retrieved = blocks[qid]
            body += (f"=== {qid} ===\nquestion date: {q['question_date']}\n"
                     f"question: {q['question']}\nmemory:\n" +
                     "\n".join("  - " + r for r in retrieved) + "\n\n")
        (ROOT / f"prompt_reader_{b}.txt").write_text(body)
    sizes = [(ROOT / f"prompt_reader_{b}.txt").stat().st_size // 1024 for b in range(6)]
    print("reader prompts KB:", sizes)

if __name__ == "__main__":
    main()
