# Keeping the alternate-reality branches: does it speed the learning curve?

**Question.** After a run, the store retains its `frontier/*` simulation
branches (with EV-gap credit). If subsequent runs KEEP that store instead of
starting fresh, does learning speed up?

**Setup.** Sequential episodes against 8 recurring trap situations (dynamics
unknown; the futures_eval game). Planner = fit rule hypotheses from records →
plan. Arms: FRESH (store wiped each episode: same 3 ambiguous seed records
forever, every rollout recomputed) vs PERSISTENT (every executed outcome
appended; rollout branches kept and reused when the same situation recurs under
the same surviving-hypothesis set).

## Results

1. **For a committing planner (picks one hypothesis — what the LLM arms did),
   persistence is the difference between converging and never converging:**
   fresh-gambler stays on the plausible-but-wrong rule forever (EV 0.48 vs
   optimal 0.605); the persistent gambler's FIRST kept outcome killed the wrong
   hypothesis (ambiguity 2→1 at episode 1) and it plans ≈optimally thereafter.
2. **For an ensemble planner, accuracy ties** (the 2-hypothesis ensemble already
   plans optimally on this pool) — but persistence still **halves compute**
   (384 vs 768 rollout sims over 24 episodes; 8/24 decisions served entirely
   from kept branches) and resolves ambiguity (ends at 1 hypothesis vs 2).
3. **Cache semantics matter:** kept branches are reusable only while the
   surviving-hypothesis set is unchanged — a world-model revision invalidates
   rollouts simulated under the old model (the credit/versioning machinery is
   what makes that safe to track).

So: yes — retain the branches. The retention benefit splits cleanly: **accuracy**
(faster hypothesis elimination — each kept outcome is training data against the
world-model ambiguity) and **compute** (recurring situations replan from kept
branches). `reuse_curves.png`.

---

## The Long Table — learning WHILE you play (`live_game.py`, `live_game.png`)

One continuous 60-round session against recurring situations; the freeze rule
is unknown AND the opponent changes it at round 30. Every round: fit hypotheses
from kept records → ensemble-plan (reusing kept branches) → act → observe →
retain.

- **Learn:** starts ambiguous (2 hypotheses), resolves in play; rounds 0–29 at
  1.000 of optimal (no-retention baseline: 0.980 forever).
- **Drift dip:** after the rule change both agents dip; briefly the confident-
  but-stale learner is WORSE than the hedging-ignorant baseline (0.960 vs
  0.980) — confidence in an outdated model underperforms ignorance.
- **Detection lags drift:** the consistency fitter only rejects the old world
  once inconsistency is undeniable (~17 rounds later), then purges 19 stale
  records and **EV snaps back to 1.000** (rounds 45–59: 0.992).
- **Retention curves:** records grow 3→50, are pruned to 31 at the purge;
  kept rollout branches grow to 24; **44/60 rounds replanned from kept
  branches** (reuse rate climbs to ~1.0 between model revisions, resets when
  the hypothesis set changes — the cache-invalidation rule doing its job).
