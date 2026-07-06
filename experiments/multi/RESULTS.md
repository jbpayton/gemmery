# Multi-agent shared memory: conflict surfacing + earned-credit adjudication

The spec's deferred 13 (branches-as-perspectives, conflict surfacing,
adjudicated merge), answered mechanically at 30 seeds with a store-backed
exemplar in exact parity.

## The game

90 hidden binary facts; 4 agents observe noisy random subsets each round with
UNEQUAL, UNKNOWN reliabilities (0.92/0.80/0.68/0.55). Each round one fresh
fact is queried, the team answers, truth is revealed, and every claimant's
walk-forward track record updates. 90 rounds x 30 seeds.

- **Branches as perspectives**: each agent `revise()`s its claim gems at
  stable `facts/f<k>` paths on its own `frontier/agent-i` branch.
- **Conflict surfacing**: the adjudicator reads every perspective at the
  queried path; disagreement is surfaced, never silently merged. Unanimity
  passes through untouched.
- **Adjudicated merge**: surfaced conflicts resolved by EARNED credit
  (beta-posterior on each agent's revealed record, log-odds vote); the
  winner's gem is `select_to_main`'d — main accumulates the team's
  adjudicated truth while every losing claim stays readable on its
  agent's branch.

## Results (30 seeds, 2,597 queries, 54% conflicted)

| arm | overall | rounds 1-30 | 31-60 | 61-90 | conflicted | clean |
|---|---|---|---|---|---|---|
| solo (no sharing, majority) | 0.881 | 0.812 | 0.887 | 0.936 | 0.822 | 0.949 |
| naive shared (last-write-wins) | **0.725** | 0.725 | 0.731 | 0.720 | 0.628 | 0.838 |
| **credit-adjudicated** | **0.918** | 0.821 | 0.938 | **0.984** | 0.892 | 0.949 |
| oracle (true reliabilities) | 0.933 | 0.857 | 0.946 | 0.988 | 0.920 | 0.949 |

`adjud - naive` on conflicted queries: **+0.264 [95% CI +0.236, +0.291]**.

## The three laws

1. **Naive sharing is worse than not sharing.** Last-write-wins (what a
   shared .md file is) scores 0.725 — below the no-sharing baseline (0.881)
   and FLAT across the run (0.725 -> 0.720): recency is not reliability, and
   an unreliable agent's late write clobbers a reliable agent's claim
   forever. Shared memory without conflict discipline destroys value.
2. **The headroom is exactly the conflict cell.** On clean (unanimous)
   queries solo = adjud = oracle = 0.949 identically; every point of
   adjudication's win comes from the 54% of queries where perspectives
   disagree (0.892 vs naive's 0.628). Conflicts are not noise to suppress —
   they are where the information is.
3. **Earned credit converges to the oracle.** Round 1-30 adjudication is
   nearly tied with solo (0.821 vs 0.812 — no track record yet: the headroom
   law again); by rounds 61-90 it reaches 0.984 vs the known-reliability
   ceiling's 0.988. The credit ledger learns WHO to believe, from outcomes
   alone, while the game is being played.

## The store exemplar (seed 0) — exact parity

`store_exemplar.py` replays seed 0 on the real machinery: 2,210 gems,
4 perspective branches, 49 conflicts surfaced -> 49 `select_to_main`
adjudications, outcome tags on every revealed claim. Its answers match the
simulation **86/86 exactly**. Post-hoc, any adjudication is auditable:
main holds the winner, `git log -- facts/f15` on each branch shows every
perspective's full revision history, and the outcome tags show why the
winner's author out-credited the losers. `browser.html` to explore.

Reproduce: `harness.py` (stats) -> `store_exemplar.py` (parity + artifact).
