"""LongMemEval v2 — mechanical upgrades only (no LLM at ingestion, still).

Changes vs v1, per Emergence's disclosed ablations:
  1. match on turns, retrieve WHOLE SESSIONS: bi-encoder top-80 turns ->
     cross-encoder rerank -> NDCG session scoring -> top-4 sessions verbatim
  2. turns no longer truncated at 700 chars (1500 now; v1's ss-assistant killer)
  3. safety net: top reranked turns from outside the chosen sessions
     (multi-session questions span more than 4 sessions)
  4. reader does brief chain-of-thought before the final JSON
Same 60 questions (meta.json), same judge protocol -> delta is attributable.
"""
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[1] / "data" / "lme"
N_SESS, CAND, SNIPS = 4, 80, 8

def main():
    from sentence_transformers import SentenceTransformer, CrossEncoder
    bi = SentenceTransformer("all-MiniLM-L6-v2")
    ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    meta = json.load(open(ROOT / "meta.json"))
    want = {m["qid"]: m for m in meta}
    d = [q for q in json.load(open(DATA / "lme_s.json"))
         if q["question_id"] in want]
    print(f"rebuilding retrieval for {len(d)} questions")

    hits, blocks = 0, {}
    for qi, q in enumerate(d):
        turns, owners, sess_text = [], [], {}
        for si, (sess, sid, date) in enumerate(zip(
                q["haystack_sessions"], q["haystack_session_ids"], q["haystack_dates"])):
            lines = []
            for t in sess:
                txt = (t.get("content") or "").strip()
                if len(txt) < 15:
                    continue
                line = f"({t['role']}): {txt[:1500]}"
                lines.append(line)
                turns.append(f"[{date}] {line[:600]}")
                owners.append(sid)
            sess_text[sid] = f"--- session {date} ---\n" + "\n".join(lines)
        emb = bi.encode(turns, batch_size=1024, convert_to_numpy=True,
                        normalize_embeddings=True, show_progress_bar=False)
        qv = bi.encode([q["question"]], normalize_embeddings=True)[0]
        cand = np.argsort(-(emb @ qv))[:CAND]
        ce_scores = ce.predict([(q["question"], turns[i]) for i in cand],
                               batch_size=256, show_progress_bar=False)
        order = cand[np.argsort(-ce_scores)]
        # NDCG-style session scoring over the reranked turn list
        sess_score = {}
        for rank, ti in enumerate(order, 1):
            sess_score[owners[ti]] = sess_score.get(owners[ti], 0) + 1/np.log2(rank+1)
        top_sids = sorted(sess_score, key=sess_score.get, reverse=True)[:N_SESS]
        # snippet safety net from OUTSIDE the chosen sessions
        extra = [turns[i] for i in order if owners[i] not in top_sids][:SNIPS]
        gold = set(q["answer_session_ids"])
        hit = bool(gold & set(top_sids)) or any(
            owners[i] in gold for i in order[:SNIPS + N_SESS]
            if owners[i] not in top_sids)
        if not q["question_id"].endswith("_abs"):
            hits += hit
        blocks[q["question_id"]] = (q, [sess_text[s] for s in top_sids], extra)
        if (qi+1) % 15 == 0:
            print(f"  {qi+1}/{len(d)}")

    n = sum(1 for m in meta if not m["qid"].endswith("_abs"))
    print(f"\noracle recall v2 (sessions+snippets): {hits}/{n} = {hits/n:.3f}")

    HDR = ("You answer questions about a user from MEMORY of past chat "
           "sessions. For each question you get its most relevant FULL "
           "sessions (dated) plus a few extra dated snippets from other "
           "sessions. For EACH question: first think briefly step by step "
           "(quote the relevant memory lines and their dates), then decide. "
           "Rules: prefer the entry LATEST before the question date when "
           "information changed; do date arithmetic carefully; if the memory "
           "does not contain the answer, the answer is exactly \"I don't "
           "know\". After reasoning through all questions, output the final "
           "answers as one JSON object mapping question id to concise answer "
           "string.\n\n")
    ids = [m["qid"] for m in meta]
    for b in range(6):
        chunk = ids[b*10:(b+1)*10]
        body = HDR
        for qid in chunk:
            q, sess, extra = blocks[qid]
            body += (f"=== {qid} ===\nquestion date: {q['question_date']}\n"
                     f"question: {q['question']}\n\n" + "\n".join(sess) +
                     "\n--- extra snippets ---\n" +
                     "\n".join("  - " + e for e in extra) + "\n\n")
        (ROOT / f"prompt_reader2_{b}.txt").write_text(body)
    print("prompt KB:", [(ROOT / f"prompt_reader2_{b}.txt").stat().st_size // 1024
                         for b in range(6)])

if __name__ == "__main__":
    main()
