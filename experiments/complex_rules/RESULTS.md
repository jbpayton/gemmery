# Complex, noisy behavioral rules — where similarity beats exact aggregation

The scale experiment showed the structured index uniquely wins for **exact
aggregation over dense sets**. This one is its mirror. People whose behavior
follows a **complex, noisy rule** — a non-linear function of several interacting
situational features, obeyed most of the time but not always — are a *learning*
problem, and there the winner flips: **similarity retrieval generalizes; exact
conditional aggregation starves.**

## Setup

Each person's rule is a random weighted sum of situational features **plus
pairwise interactions** (so it is genuinely non-linear, not a single tell),
thresholded, then flipped ~15% of the time (the "doesn't always" part → Bayes
ceiling ≈ 0.85). We give a long history of `(situation → decision)` and ask: what
will they do in a new situation?

## Deterministic result (12 features, 2,500 games/person)

The exact current-situation cell holds **0.58 samples on average** — almost
always empty.

| memory-access strategy | accuracy (Bayes ceiling 0.85) |
|---|---|
| marginal base-rate (ignores situation) | 0.50 |
| **exact conditional lookup (structured filter)** | **0.61** |
| **similarity retrieval (kNN over situations)** | **0.78** |

`complexity_flip.png` sweeps rule complexity: at ≤8 features (dense cells) exact
and similarity both track Bayes; past ~10 features the exact conditional
**collapses toward chance** while similarity holds near ceiling. The marginal
aggregate is useless throughout — the behavior *depends on the situation*, so
ignoring it (or averaging over all situations) tells you nothing.

## Real-agent confirmation (in-context rule induction, n=20)

Three Claude sub-agents predicted a held-out person's decisions given the same
40-example budget, selected two ways: `md` = 40 **random** past situations
(induce the global rule); `gemmery` = the 40 **most similar** past situations per
query (retrieval).

| arm (n=20, noisy) | accuracy |
|---|---|
| cold (no examples) | 0.55 |
| 40 **random** examples (induce global rule) | 0.50 |
| 40 **similar** examples (retrieval) | 0.60 |

Two honest wrinkles:
1. **Similar > random (0.60 vs 0.50)** — retrieval strategy helps the LLM too;
   a random sample of 40 was not enough to *induce* a 12-feature interaction rule
   (it actually did slightly worse than guessing — a small sample of a complex
   rule can mislead an inducer).
2. **But the LLM under the similar examples (0.60) underperforms the mechanical
   kNN majority over the *same* neighbors (0.78).** On a noisy statistical
   prediction, a plain majority-vote is more robust to the 15% deviations than
   the model reasoning example-by-example — it overthinks. The lesson: retrieve
   the similar set (that part matters), then *aggregate* it simply rather than
   reason over it.

## Why this matters for the whole picture

Put beside the previous results, the honest conclusion is that **no single memory
substrate is best — the right retrieval depends on the query:**

| query | read-all | vector / similarity | exact structured index |
|---|---|---|---|
| rare existence ("did X ever happen?") | ✗ | ✓ | ✓ |
| exact aggregate over dense set ("how often / who most?") | ✗ | ✗ | ✓ |
| **complex noisy rule ("what will they do here?")** | ✗ | **✓** | ✗ (cells starve) |

Similarity retrieval and exact aggregation are *complementary opposites*: one
generalizes across a sparse high-dimensional space, the other computes exact
totals over dense sets. A system with **both** layers — which Gemmery has (an
embedding index *and* a columnar index over the same DAG) — can serve both,
where a pure-markdown store (text/vector only) or a pure-SQL store (exact only)
each covers just one. That, not "structure always wins," is the defensible case
for the two-layer design.

Reproduce: `python experiments/complex_rules/rules_demo.py`,
`.venv/bin/python experiments/complex_rules/plot.py`,
`python experiments/complex_rules/build_llm.py` then `score_llm.py`.
