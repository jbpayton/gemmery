#!/usr/bin/env python3
"""Reproduce the transfer-recall experiment (escape #1 + #2, spec §0).

Compares one-shot vs browse at *surfacing* a cross-surface, same-method gem.
``agent_queries.json`` holds reformulations produced by real Claude sub-agents
(committed, so this reproduces without re-running models).

    # offline (dependency-free hashing embedder):
    python experiments/transfer_recall/run.py

    # real embeddings (needs `pip install 'gemmery[embed]'`):
    python experiments/transfer_recall/run.py --embedder st
"""
import argparse
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from gemmery.eval.recall import transfer_recall_report

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedder", choices=["hashing", "st"], default="hashing")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    embedder = None
    if args.embedder == "st":
        from gemmery.index import SentenceTransformerEmbedder
        embedder = SentenceTransformerEmbedder()

    aq = json.load(open(HERE / "agent_queries.json"))
    rep = transfer_recall_report(embedder=embedder, agent_queries=aq, top_k=args.top_k)

    print(f"embedder: {rep.embedder}   (n={rep.n}, top_k={rep.top_k})")
    print(f"transfer recall@{rep.top_k}:")
    print(f"  one-shot   (problem surface)      = {rep.oneshot_recall:.2f}")
    print(f"  browse     (MockPolicy marks)     = {rep.browse_mock_recall:.2f}")
    print(f"  browse     (Claude reformulation) = {rep.browse_agent_recall:.2f}")
    print(f"one-shot misses:        {rep.oneshot_misses}")
    print(f"recovered by browse:    {rep.recovered_by_agent}")
    print(f"lost by browse:         {rep.lost_by_agent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
