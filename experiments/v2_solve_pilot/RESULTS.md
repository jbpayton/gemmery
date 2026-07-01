# v2 end-to-end solve pilot — results

**Question.** On the open-ended, objective-scored v2 tasks, does giving a real
Claude agent the transferable *approach* (as it would surface from memory)
improve its scored solution over solving cold — at matched model-calls? This is
the application half of the thesis (arm1 vs arm3); the retrieval half was shown
separately (`experiments/transfer_recall`, browse recall 0.79→1.00).

**Setup.** 16 v2 tasks, leave-one-out. Ten Claude sub-agents (5 batches ×
{with-memory, cold}) each solved a batch, blind to the verifier and to which arm
they were. Batches mix distinct approaches so the cold arm cannot transfer within
a batch. Each solution graded by the live `ScoredVerifier`. "Memory" = the
approach as discovered on a different-surface sibling, framed as a note from an
unrelated past project.

## Result: a clean null

| | mean score | success @ threshold |
|---|---|---|
| **with memory** | 1.000 | 16/16 |
| **cold** | 1.000 | 16/16 |
| **Δ** | **+0.000** | **0** |

Δ = 0.00 on every task, every family. Both arms hit the ceiling.

## Why (this is the interesting part)

The null is not noise — it is two mechanisms, both visible in the agents' own
notes:

1. **No headroom.** A capable model already knows the strong approach for these
   tasks *cold*. The no-memory agents independently reached for 0/1-knapsack DP,
   LPT + branch-and-bound (better than the reference LPT), true sliding-window
   rate limiting, prefix sums, and hash-set single-pass — often **beating the
   reference solutions**. There is no gap for memory to fill.

2. **Capable agents critically evaluate memory.** On the knapsack and
   load-balancing tasks the *memory-arm* agents explicitly **rejected** the
   hinted approach — "greedy value/cost is not optimal for 0/1 selection", "LPT
   is only a 4/3 approximation" — and implemented the exact optimum instead.
   Memory weaker than the model's own knowledge is correctly discarded, so it
   cannot even hurt (no negative effect either).

## What this means

This reproduces the GitOfThoughts null **at the application layer**, and sharpens
it into a precise condition. Memory can raise solve quality only when:

```
   the model would fail (or solve poorly) cold
   AND the stored approach is better than what the model produces unaided
   AND the model recognizes it as such
```

None of those hold here: the model solves cold at the ceiling, and where the
memory was weaker it was thrown out. The bottleneck for *demonstrating* memory
value is therefore **task-difficulty calibration**, not the memory machinery.

Combined with the retrieval result, the full chain reads: browsing *finds* the
transfer approach reliably (✓), but on tasks within the model's cold competence,
*having* it changes nothing (✓ null, understood). Gemmery's kill-switch
philosophy did its job — it surfaced a load-bearing negative result cheaply.

## Next iteration (what a task set that could show a positive needs)

- **Beyond cold competence.** Approaches the model does *not* reliably invent:
  domain-specific tricks, non-obvious problem reformulations, hard-won project
  lessons ("this API silently truncates", "that solver diverges unless you seed
  it this way"), or compositional multi-step methods.
- **Where the stored approach is decisively better** than the model's default,
  and the model can't trivially re-derive it under the compute budget.
- **Calibrate against the cold baseline first:** only keep tasks where the cold
  arm scores well below ceiling. (The `validate_discrimination` gate ensures a
  *naive* solution fails; this pilot shows we *also* need the *model's cold*
  solution to fail — a stricter, model-relative headroom check worth adding.)

Reproduce the scoring: `python experiments/v2_solve_pilot/score.py`
(solutions in `out_*/` are the actual agent outputs; agents are non-deterministic,
so re-running the agents will vary, but the committed solutions reproduce Δ=0).
