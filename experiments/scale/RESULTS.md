# Beyond the context window — when structure becomes mandatory

Every earlier experiment let a flat markdown scratchpad *tie* Gemmery, because
the whole history still fit in a context window, so "read it all" worked. This
one removes that escape: the decision hinges on a **rare fact scattered across a
history far larger than any context window**, so a read-based memory — which is
context-bounded — physically cannot get the answer, while Gemmery's derived
index answers it exactly.

## The task ("alibi check")

You have played **100,000 games** with the same 8 opponents. This game a player
claims a power role (Engineer / Doctor / Guardian Angel / Guard). Is it a lie?
It is a lie — marking them a Gnosia — **iff that opponent has never once truly
held that role in their entire career.** An honest player may be claiming a role
they hold only *rarely* (≈5 games out of 100,000). To clear them you must know
those 5 games happened — a rare-event existence query over the full history.

Memory size: **800,000 records ≈ 32 MB ≈ 8.0 M tokens** — about **40× a
200K-token context window.** A reader can hold ~2.5% of it.

## Deterministic result (n=40 decisions)

| access to the 8M-token history | accuracy (catch the lying Gnosia) |
|---|---|
| cold (no memory) | 0.45 |
| markdown, read as much as fits (~2.5%) | **0.53** |
| **Gemmery index (exact `SELECT DISTINCT true_role`)** | **1.00** |

Accuracy vs how much of the history the reader can hold (`context_wall.png`):

```
  % readable :  1%   2%   5%  10%  20%  40%  70% 100%
  accuracy   : .53  .53  .60  .60  .70 1.00 1.00 1.00
                     ^ a context window holds ~2.5%
```

The read-based approach only reaches ceiling once it can hold **≥40%** of the
history. A context window holds 2.5%, so it is pinned near chance. The index is
**1.00 regardless of context size** — it queries the whole store in O(index).

## Real-agent confirmation (n=6)

Three Claude sub-agents applied the same rule with three memory accesses:
`gemmery` (the index's exact per-player career support, ~1 KB), `md` (a hefty
~300 KB / 8,000-record excerpt of the raw notes — as much as fits, with grep
allowed), `cold` (none).

| arm | accuracy (n=6) |
|---|---|
| cold | 1/6 = **0.17** |
| markdown (300 KB slice + grep) | 3/6 = **0.50** |
| **Gemmery (exact index)** | 6/6 = **1.00** |

The markdown agent landed exactly on the coin-flip the theory predicts: it can
see two players who *look* like liars but cannot reach the rare career fact that
would clear the honest one, so it guesses. The Gemmery agent, handed the exact
per-player role support the index computes over the whole store, was perfect.

## The fairer baseline (correction): vector search over the markdown

The `read-what-fits` baseline above is a strawman — at scale you would not *read*
the notes, you would **vector-search** them (RAG). Adding that arm changes the
result, and the correction matters (`vector_demo.py`, real all-MiniLM-L6-v2
embeddings over 200K records):

| query type | read-what-fits | **vector RAG** | **exact columnar index** |
|---|---|---|---|
| **rare existence** ("has P ever held role R?") | 0.53 | **1.00** | 1.00 |
| **exact aggregate** ("who was the Gnosia most often?", close counts) | 0.43 | **0.57** | **1.00** |

- **On the rare-existence query, vector search TIES the index** — recall@50 =
  40/40; the ~5 alibi records are near-duplicates of the query, so top-k finds
  them among 200K. So the earlier "structure wins" headline was **too strong**:
  for *retrieval/existence*, a flat file + embeddings is as good as the columnar
  index. Read-it-all is the only thing that actually fails there.
- **On the exact-aggregate query, both read (0.43) and vector (0.57) fail; only
  the exact index (1.00) works.** Top-k retrieval returns a *sample*, and you
  cannot compute an exact `SUM`/`COUNT`/`AVG` over tens of thousands of matching
  records from a sample of 200 — so close totals are indistinguishable. The
  columnar `SUM(is_gnosia) GROUP BY player` is exact.

## What actually wins, and where

Corrected, the boundary is sharp and not about "context window" per se:

- **Retrieval / similarity / existence:** vector search over a flat markdown file
  matches Gemmery's index. Structure is *not* required (it is an efficiency and
  provenance win, not accuracy). Read-it-all fails only because it can't hold the
  history — but vector-RAG over that same file is fine.
- **Exact aggregates / analytics over large sets** (counts, rates, "how often",
  ranking by a total): *no* bounded read and *no* top-k retrieval can do it —
  only a structured index with real aggregation. This is the one capability that
  is genuinely unique to the columnar layer.

That second row is not a side-note for Gemmery — it *is* the credit system (§7):
signed, earned credit is an **aggregate over the whole dependency DAG** ("used in
12, vindicated in 9"; marginal contribution across the corpus). Vector recall
can't compute it; the columnar index can. So the honest claim is narrower and
sturdier than the first headline: **memory content helps when the model lacks it;
vector-RAG over a text file handles retrieval as well as the DAG; the structured
index earns its keep specifically for exact aggregation — which is exactly what
earned credit requires.**

(Scale note: no git commits at 800K records — the columnar index is bulk-loaded,
which is legitimate because the index is derived/disposable by design; at real
scale Gemmery captures in batches and rebuilds the index from the store.)

Reproduce: `python experiments/scale/scale_demo.py` (deterministic + sizes),
`.venv/bin/python experiments/scale/vector_demo.py` (vector RAG + aggregate),
`.venv/bin/python experiments/scale/plot.py` (curve),
`python experiments/scale/build_llm.py` then `score_llm.py` (agent confirmation).
