"""Fairer baseline: vector search (RAG) over the markdown records.

At scale you would not *read* the notes — you would embed the records and
retrieve the relevant ones. This adds that arm to the alibi-check task and
measures it honestly against the exact columnar index.

Prediction: the alibi task is a RARE-EXISTENCE query ("has P2 ever truly held
Guard?"), and the ~5 true-hold records are near-duplicates of that query — so
top-k vector search should surface them and TIE the exact index. That would show
the earlier "read-what-fits" baseline was too weak, and that structure only wins
when the query is something vector search *can't* do (see aggregate_demo.py).
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scale_demo import (generate, make_tests, build_index, index_support,  # noqa: E402
                        PERSONAS, ROLES, accuse)

GAMES = 25_000  # 200k records — still ~10x a context window, faster to embed
TOPKS = [5, 10, 20, 50, 100]


def record_doc(rec) -> str:
    g, p, is_g, true_role, claimed = rec
    role = "Gnosia" if is_g else true_role
    return f"{p} true-role {role} claimed {claimed or 'nothing'} game {g}"


def main():
    import random
    from sentence_transformers import SentenceTransformer

    defs, rare_games, records = generate(GAMES)
    con = build_index(records)
    tests = make_tests(defs, records)

    print(f"records: {len(records):,}  (~{sum(len(record_doc(r)) for r in records)//1_000_000} MB of docs)")
    print("embedding all records (real vector search over the markdown)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    docs = [record_doc(r) for r in records]
    emb = model.encode(docs, batch_size=2048, convert_to_numpy=True,
                       normalize_embeddings=True, show_progress_bar=False).astype(np.float32)

    def vector_support_factory(k):
        cache = {}

        def support(p):
            if p in cache:
                return cache[p]
            found = set()
            for R in ROLES:
                q = model.encode([f"{p} true-role {R}"], normalize_embeddings=True)[0]
                top = np.argpartition(-(emb @ q), k)[:k]
                for idx in top:
                    g, pp, is_g, tr, cl = records[idx]
                    if pp == p and (not is_g) and tr == R:  # a genuine hold, retrieved
                        found.add(R); break
            cache[p] = found
            return found
        return support

    def score(support_fn, seed=0):
        rng = random.Random(seed)
        return sum(accuse(t["claims"], support_fn, rng) == t["gnosia"]
                   for t in tests) / len(tests)

    idx_acc = score(lambda p: index_support(con, p))
    print(f"\nexact columnar index: {idx_acc:.2f}")
    print("vector search over markdown (RAG), by top-k:")
    for k in TOPKS:
        print(f"  top-{k:<3}: {score(vector_support_factory(k)):.2f}")

    # recall probe: does vector retrieve the honest player's RARE true-hold?
    k = 50
    hits = 0; tot = 0
    for t in tests:
        p, R = t["honest_rare"], defs[t["honest_rare"]]["rare"]
        tot += 1
        q = model.encode([f"{p} true-role {R}"], normalize_embeddings=True)[0]
        top = np.argpartition(-(emb @ q), k)[:k]
        if any(records[i][1] == p and not records[i][2] and records[i][3] == R for i in top):
            hits += 1
    print(f"\nrare-hold recall@{k}: {hits}/{tot} = {hits/tot:.2f} "
          "(did vector find the ~5 alibi records among 200k?)")

    # ------------------------------------------------------------------ #
    # The query vector search CANNOT do: an EXACT AGGREGATE over a big set.
    # "Who has been the Gnosia most often across our shared history?" The top
    # career counts are close, so you need the exact total — top-k retrieval can
    # only sample it. columnar index: SUM(is_gnosia) GROUP BY player -> exact.
    # ------------------------------------------------------------------ #
    import itertools
    exact_count = {p: 0 for p in PERSONAS}
    per_player_idx = {p: [] for p in PERSONAS}
    for i, r in enumerate(records):
        per_player_idx[r[1]].append(i)
        if r[2]:
            exact_count[r[1]] += 1

    # vector estimate of each player's Gnosia-rate: retrieve top-k records for
    # "{p}" and take the fraction that are Gnosia (a k-sized sample).
    ksamp = 200
    vec_rate = {}
    for p in PERSONAS:
        qp = model.encode([f"{p} game record"], normalize_embeddings=True)[0]
        top = np.argpartition(-(emb @ qp), ksamp)[:ksamp]
        mine = [i for i in top if records[i][1] == p]
        vec_rate[p] = (sum(records[i][2] for i in mine) / len(mine)) if mine else 0.0

    # read-window estimate: fraction Gnosia among each player's records in a
    # 5%-of-history slice (a context-window-sized read).
    win = records[:int(len(records) * 0.05)]
    read_cnt = {p: [0, 0] for p in PERSONAS}
    for r in win:
        read_cnt[r[1]][0] += r[2]; read_cnt[r[1]][1] += 1
    read_rate = {p: (c[0] / c[1] if c[1] else 0.0) for p, c in read_cnt.items()}

    pairs = list(itertools.combinations(PERSONAS, 2))
    close = [(a, b) for a, b in pairs if abs(exact_count[a] - exact_count[b]) < 120]

    def pair_acc(rate, subset):
        ok = 0
        for a, b in subset:
            truth = exact_count[a] > exact_count[b]
            ok += (rate[a] > rate[b]) == truth
        return ok / len(subset) if subset else float("nan")

    print("\n--- EXACT-AGGREGATE query: 'who was the Gnosia more often?' ---")
    print(f"career counts (exact): {sorted(exact_count.values(), reverse=True)}")
    print(f"all {len(pairs)} pairwise decisions | {len(close)} are 'close' (<120 apart):")
    print(f"  exact columnar index : all={pair_acc(exact_count, pairs):.2f}  close={pair_acc(exact_count, close):.2f}")
    print(f"  vector RAG (k={ksamp} sample): all={pair_acc(vec_rate, pairs):.2f}  close={pair_acc(vec_rate, close):.2f}")
    print(f"  read 5% window       : all={pair_acc(read_rate, pairs):.2f}  close={pair_acc(read_rate, close):.2f}")


if __name__ == "__main__":
    main()
