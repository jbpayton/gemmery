# Branch prediction in the reasoning loop — does it improve gameplay?

**Question.** Make the forked-futures apparatus part of the *reasoning*: does an
agent that receives simulated branch rollouts decide better than one reasoning
directly? Scored on gameplay (true EV of picks), on decisions built to punish
myopia.

**Setup.** 12 Day-1-vote scenarios mined so that in 8 of them the myopic move
(vote the top suspect) is NOT EV-optimal (gaps 0.10–0.14; night-freeze dynamics
make a lower-belief vote better). Both arms get identical rules + beliefs;
the **branch arm** additionally gets per-candidate simulated timelines per wolf
hypothesis (no aggregated EVs — it must weigh); the **direct arm** may simulate
mentally. All 48 explored futures are **materialized as real git branches**
(`frontier/s<k>/vote-<v>` with plan + rollout gems; the branch-arm prompt is
assert-verified to be derived from store content). After scoring, both arms'
picks are recorded as decision gems consuming their chosen rollout; chosen
futures selected to main; all 48 futures credited by EV gap (opportunity cost).

## Result: a tie — at the ceiling

| policy | EV | optimal picks | trap-cell optimal | fell for myopic |
|---|---|---|---|---|
| random | 0.537 | — | — | — |
| argmax-belief (myopic) | 0.543 | 4/12 | 0/8 | 8/8 |
| **direct (mental simulation)** | **0.624** | **12/12** | **8/8** | 0/8 |
| **branch (rollouts provided)** | **0.624** | **12/12** | **8/8** | 0/8 |
| EV-optimal ceiling | 0.624 | 12/12 | 8/8 | 0/8 |

Both arms played perfectly, beating the myopic policy by +0.08 EV and dodging
every trap. **No accuracy lift from providing the branches** — because of *how*
the direct arm won: its own report says it "computed by exact enumeration of
the night-freeze and Day-2 dynamics for every (vote, wolf) pair." Given fully
stated deterministic rules, **a strong model spontaneously constructs the
branch apparatus in its head.** The externalization added nothing it couldn't
build itself.

What externalization DID buy, measured:
- **Latency:** branch arm 28s vs direct arm 111s (4×) — the simulation was
  precomputed instead of re-derived.
- **Auditability:** the direct arm's 48-future enumeration happened invisibly
  in its reasoning and is unverifiable; the branch arm's futures are 48 git
  branches with rollouts, picks recorded as gems consuming them, and
  opportunity-cost credit on every road not taken.

## Honest read, in the arc's terms

This is the **headroom result again, one level up**: handing the model a
simulation it can already run mentally is like handing it a textbook method it
already knows (v2 solve pilot, Δ=0). Branch-prediction-in-reasoning should
produce an *accuracy* lift precisely when mental simulation breaks:

1. **World model not in the prompt** — dynamics that must be assembled from
   memory (learned tells, credit-weighted reliabilities) rather than stated rules;
2. **Trees too big/deep to hold in the head** — where enumeration exceeds
   working context and externalized rollouts + credit become the only bookkeeping;
3. **Stochastic dynamics** needing many rollouts per branch.

Until then, its measured value in gameplay is speed and a fully auditable
decision record — which for a memory system is not a consolation prize; it is
the product.

Reproduce: `build_eval.py` (mine traps, emit prompts) → `materialize.py`
(futures as git branches; prompt provably store-derived) → two arm agents →
`score.py` → `record.py` (picks + credit into the store).
