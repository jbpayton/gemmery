# Transfer-recall experiment — results

**Question.** Does *browsing* (an agent issuing several reformulated, solution-shape
queries) surface a cross-surface, same-method ("transfer") gem better than a
single one-shot lookup? This isolates escapes #1 (browsing > lookup) and #2
(index on solution shape) — the cell GitOfThoughts controlled away by holding the
agent fixed (spec §0).

**Setup.** 24-task seed dataset (6 solution-schemas × 4 surface domains). Memory
holds one gem per task. Leave-one-out: each query task's own gem is excluded, so
a hit must come from a *different-surface, same-method* gem. Metric: transfer
recall@5. The "Claude reformulation" arm uses search queries produced by Claude
sub-agents (committed in `agent_queries.json`), each blind to the memory and to
the schemas — i.e. the `AnthropicPolicy.reformulate` step, run out of band so the
result reproduces without re-running models.

## Numbers

| transfer recall@5 | one-shot (problem surface) | browse — MockPolicy (marks) | browse — Claude reformulation |
|---|---|---|---|
| **real embeddings** (all-MiniLM-L6-v2) | 0.79 | 0.25 | **1.00** |
| hashing (dependency-free) | 0.50 | 0.25 | **0.96** |

Real embeddings, one-shot **missed** the transfer gem on 5 tasks — all in the
method-transfer cell: `memo_game, memo_bio, memo_web, acc_log, acc_chat`
(memoize / accumulator across distant surfaces). Claude reformulation
**recovered all 5, with zero regressions.** The agent's queries used method
vocabulary ("memoize", "cache expensive recompute", "accumulate then join",
"string buffer") that matched the *solution-shape* index where one-shot's
surface query did not.

Reproduce:

```bash
python experiments/transfer_recall/run.py              # offline, hashing
python experiments/transfer_recall/run.py --embedder st   # real embeddings ([embed] extra)
```

## What this shows

- **The retrieval premise of Gemmery holds.** At matched intent, browsing with
  real reformulation strictly dominates one-shot lookup at *finding* transfer
  methods, and recovers exactly the low-problem-similarity / high-solution-
  similarity cases that defeat surface lookup.
- **The deterministic policy — not retrieval — was the bottleneck.** `MockPolicy`
  (0.25) is the weakest arm in every condition; swapping in a real agent fixes it.
  This is consistent with the offline harness finding and explains it.

## What this does NOT show (read before over-claiming)

- **This is retrieval recall, not task success.** It shows browse *surfaces* the
  transfer gem; it does not yet show that having the gem *raises solve accuracy*.
  The seed verifier tasks are easy enough for a capable model to solve cold
  (no headroom), so the end-to-end efficacy question — the actual Phase-0
  go/no-go (arm1 vs arm3 at matched compute) — is still open and needs harder
  tasks where the method is the bottleneck.
- **n = 24, single run, one constructed dataset, one embedder.** Not a
  pre-registered confirmation. GitOfThoughts' +15pp died from n=40 to n=98 —
  treat this as exploratory evidence that the mechanism is real, not as the
  green light.
- It measures the `reformulate` step only (+ union retrieval), not the full
  assess/recognition loop.

**Bottom line.** The escape mechanism is real and reproducible at the retrieval
layer with a real agent. That is necessary, not sufficient: it earns the right to
run the harder, pre-registered, end-to-end efficacy experiment — it does not
replace it.
