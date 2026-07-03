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
