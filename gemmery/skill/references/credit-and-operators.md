# Credit and operators (spec §7-8) — GATED

> **Do not use these features yet.** They are gated behind a *replicated*
> Phase-0 win over the empty-memory control at matched compute (spec §10.3).
> `scripts/credit.py` and `scripts/promote.py` are inert and will tell you so.
> This document is here so you understand *what* is being deferred and *why*.

## Why gated

There is strong recent evidence (GitOfThoughts, arXiv:2606.14470) that
cross-problem agent memory does not improve accuracy on novel problems in any
substrate, and that the one apparent win collapsed under pre-registered
replication. Gemmery bets this null is an artifact of *how* they retrieved
(one-shot static lookup), not a law about memory. Credit and operator promotion
are the expensive machinery that only pays if that bet is right — so they are
downstream of a gate that can say no. Build them only after:

```bash
python -m gemmery.eval.run_phase0           # the kill-switch
# => GREEN-LIGHT to build credit/operators: True   (and it must REPLICATE)
```

## Credit (§7), when un-gated

- Credit flows **backward along dependency edges** (`consumed[]`), asynchronously,
  whenever a downstream outcome resolves. It is **continuous and signed** — a
  marginal-contribution coefficient, not a verdict.
- Start **correlational** (co-occurrence-weighted): across a large corpus, a gem
  that merely lies around nets toward zero; a load-bearing one drifts positive; a
  harmful one goes negative. Variation performs the ablation for free.
  Counterfactual ablation is an opt-in for high-stakes gems, not the default.
- **Horizon/decay required** (`λ, max_depth`): undamped propagation diffuses
  credit until everything carries a little and the signal is gone.
- **Dangling resolution (§7.3):** a stored fact starts `pending`. When a later
  task consumes and resolves it, that enqueues a credit update — itself a logged
  decision. A fact becomes worth its track record, not its storage-time credence.
- **Why-aware credit (§7.4):** the `reasoning` field lets credit *extrapolate*
  past sampled support — predict X works on unseen Z by checking whether Z
  carries the feature X broke on. Similarity transfer only interpolates.

## Operators (§8), when un-gated — manufacturing copyability

- Once credit is signed-continuous and bound to preconditions, an action's value
  is a **surface over precondition space**, not a scalar. "Works for Z, not Y" is
  not a contradiction — it's the surface having different sign in different
  regions. An operator's **applicability mask** is where the surface stays
  positive.
- **Promotion = abstraction by partitioning.** Cluster gems sharing a
  precondition shape + action type; where outcomes are heterogeneous, split on
  the precondition feature that best predicts the split — information-gain
  splitting on the **credit signal**, not class labels.
- **Stopping rule is the central knob (regularize it).** Too coarse re-imports
  "X fails" as under-conditioning; too fine manufactures superstitions ("X fails
  on Tuesdays"). Require minimum-support **and** a complexity penalty; tune the
  stopping depth, never hardcode it.
- **Near-executable operators (§8.3):** a precondition mask to *match* + a typed
  action to *bind* — closer to PDDL instantiation than free-form in-context
  abstraction. The structural bet: convert "abstract a method from prose" (which
  failed) into "bind variables in a matched operator." Operators live on the
  `operators` branch, indexed by applicability mask.
