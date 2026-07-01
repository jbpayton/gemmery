# Gemmery — versioned agent memory with earned credit

> A *gemmery* is where rough stones are kept, cut, and turned into gems. Gemmery
> stores an agent's decisions and knowledge as an immutable, branchable **git
> DAG**: each captured record is a **gem**, and patterns that earn their keep
> through repeated, test-verified use get **cut** into reusable operators.

It binds success to explicit tests rather than a global scalar, lets credit flow
backward to whatever was actually load-bearing, and is delivered as a
Claude-style **skill** — capture and retrieval are *intentional agent actions*,
not a background daemon.

## Findings scorecard

Full cross-experiment comparison of every memory approach × every query type: **[FINDINGS.md](FINDINGS.md)** (capstone matrix in `experiments/summary_matrix.png`).

## The build is gated, not linear

This project is a bet against a strong recent null (GitOfThoughts,
arXiv:2606.14470): that cross-problem agent memory doesn't help on novel problems
in *any* substrate. Gemmery bets that null is an artifact of *how* they retrieved
(one-shot static lookup), not a law — and stakes that bet on two escapes:
**browsing instead of lookup**, and **indexing on solution shape instead of
problem surface**.

So the expensive machinery is **downstream of a kill-switch that can say no.**

| Phase | Component | Status |
|---|---|---|
| 0 | `eval/` — pre-registered, compute-matched ablation | **built, runs, can refuse** |
| — | `store/` `index/` `browse/` — minimum to feed Phase 0 | **built + tested** |
| — | `skill/` — the delivered skill (capture + browse live) | **built** |
| 1 | `credit/` — earned, signed, deferred credit | **gated stub** |
| 2 | `operators/` — promotion / operator induction | **gated stub** |
| — | `effects/` — reversibility + compensation | **gated stub** |

`credit` and `operators` are built **only on a *replicated* win** of
browse+memory over browse+empty-memory at matched compute (spec §10.3). Anything
less and Gemmery ships as an audit/coordination system (which the evidence
already supports) with the smarter-agent claim shelved.

## Quickstart

```bash
pip install -e .                      # pygit2 + numpy; extras: [embed] [llm] [dev]

# Phase 0 — the kill-switch (this is what gates everything else)
python -m gemmery.eval.run_phase0     # pre-register → feasibility gate → exploratory → confirm
python -m gemmery.eval.run_phase0 --gain 0.0   # prove it can REFUSE (memory inert)

# Use the memory (intentional capture + browse)
export GEMMERY_STORE=./.gemmery-store
echo '{"kind":"decision","action":{"name":"retry_with_backoff"},
       "reasoning":"transient idempotent retries with backoff",
       "tests":[{"id":"t_net"}],"action_type":"retry_backoff",
       "domain":["networking"],"precondition_shape":["transient","idempotent","retry"]}' \
  | gemmery capture -
gemmery browse "how did we handle flaky network calls" --budget 8
gemmery decorrelation                 # the §10.2 dataset feasibility report
```

## What Phase 0 actually decides

Three arms at a **matched compute budget** (spec §10.1):

1. `browse + memory` — the full browse loop over a populated store.
2. `one_shot + memory` — a single static top-k lookup (the GitOfThoughts modality).
3. `browse + empty memory` — **the kill-switch control**: same loop, same budget,
   empty store.

The only comparison that proves memory is load-bearing is **arm 1 vs arm 3**.
Browsing is extra model calls, and extra test-time compute was the *only* lever
GitOfThoughts found that reliably helped — so if memory can't beat the same loop
over an empty store, we've merely rediscovered that thinking longer helps. Arm 3
is not optional, and the per-arm compute report is part of every result artifact.

The harness is built to be **falsifiable**: with no real transfer it returns *no
green light*; the `eval` tests assert both directions.

## Early signal: the escape mechanism is real at the retrieval layer

Using **Claude sub-agents as the reformulation policy** (no API key — the model
in the loop is sub-agents) + real sentence-transformer embeddings, browsing
recovers the cross-surface transfer gems that one-shot lookup misses:

| transfer recall@5 (real embeddings) | recall |
|---|---|
| one-shot (problem-surface query) | 0.79 |
| browse (Claude solution-shape reformulation) | **1.00** |

All 5 of one-shot's misses (memoize/accumulator across distant surfaces — the
exact method-transfer cell) were recovered, zero regressions. This is necessary,
not sufficient: it's *recall*, not solve accuracy, at n=24 — it earns the right
to run the pre-registered end-to-end efficacy experiment, it doesn't replace it.
Reproduce: `python experiments/transfer_recall/run.py [--embedder st]`. Details
in `experiments/transfer_recall/RESULTS.md`.

## Design invariants (non-negotiable — spec §1)

1. **Immutable record, mutable valuation.** Commits are never rewritten; scores
   and credit are append-only git notes.
2. **Success is test-bound, continuous, signed.** `{test_id → score ∈ [-1,+1]}`,
   never a global boolean.
3. **Three-valued judgment.** `pending` (⊥) ≠ `0.0` ≠ negative.
4. **Two graphs recorded separately.** History (git parents) is free; the
   dependency graph (`consumed[]`) is recorded explicitly — credit flows along it.
5. **Intentional capture and retrieval.** Never a background hook; the decision
   to record is itself signal.
6. **Git is the source of truth; the index is derived and rebuildable.**
7. **Selection over merge for reasoning.** Explore branches, cherry-pick the
   winner to `main`.
8. **Git rewinds state, not the world.** Irreversible effects need compensation,
   not naive rewind.
9. **Capture is cheap** (< 25 ms). Measured median here: ~2 ms.

## Layout

```
gemmery/
├── model.py        # the gem: envelope + typed bodies (sum type)
├── valuation.py    # append-only success/credit notes (mutable valuation)
├── store/          # git-native capture / notes / tags / dependency edges
├── index/          # columnar (SQLite) + embedding; hybrid retrieve; rebuildable
├── browse/         # the agentic loop: budget, permeability, policies (the crux)
├── eval/           # Phase 0: dataset + decorrelation, 3 arms, prereg, replication
├── credit/         # GATED stub (§7)
├── operators/      # GATED stub (§8)
├── effects/        # GATED stub (§9)
├── skill/          # SKILL.md + scripts/ + references/ + evals/
└── cli.py          # `gemmery` entry point
```

## Tests

```bash
python -m pytest        # store timing, index parity, browse budget/membrane, kill-switch both ways
```

See `IMPLEMENTATION_NOTES.md` for design decisions, the offline-baseline finding,
and what a real efficacy run needs.
