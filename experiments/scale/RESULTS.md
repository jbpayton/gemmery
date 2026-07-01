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

## Why this is the real point

Gemmery's structural advantages — selective retrieval, columnar aggregates,
immutable records, browsing — are *conveniences* while the history fits in
context (Werewolf and Gnosia showed a flat `.md` file ties it there). Past the
context wall they become **the only thing that works**: a flat file can be
grepped, but a rare fact returns either nothing (missed by the slice) or, for a
common entity, more rows than fit — while the index answers the exact
existence/aggregate query in one shot. That is the regime where "git is the
source of truth; the index is a derived, rebuildable retrieval layer"
(Invariant 6) stops being architecture and starts being the whole game.

(Scale note: no git commits at 800K records — the columnar index is bulk-loaded,
which is legitimate because the index is derived/disposable by design; at real
scale Gemmery captures in batches and rebuilds the index from the store.)

Reproduce: `python experiments/scale/scale_demo.py` (deterministic + sizes),
`.venv/bin/python experiments/scale/plot.py` (graph),
`python experiments/scale/build_llm.py` then `score_llm.py` (agent confirmation).
