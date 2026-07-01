# The gem schema (spec §2)

A gem is one captured unit — a decision, observation, or piece of knowledge. It
is simultaneously a Hoare triple `{pre} action {post}`, a STRIPS/PDDL operator
instance, and an RL transition `(s, a, r, s′)`. One record type serves episodic
memory, a planning-operator library, and procedural skills at once.

A gem is a **shared envelope** plus a **typed body** (a sum type — do not flatten
into one nullable row).

## Envelope (every gem)

| field | meaning |
|---|---|
| `id` | content hash — the git commit SHA (assigned on capture) |
| `parents` | history-graph parent SHAs (git gives this) |
| `kind` | `decision` \| `observation` \| `knowledge` |
| `provenance` | actor (agent/model id), session id, timestamp |
| `cost` | tokens / wall-time / tool-calls spent producing this gem |
| `reversibility_class` | `pure` \| `reversible` \| `compensable` \| `irreversible` |
| `index_keys` | `precondition_shape[]`, `action_type`, `domain[]`, `test_ids[]` |
| `consumed[]` | dependency-graph out-edges: gem ids this gem used. **Required for credit.** |
| `incited_by` | dependency-graph in-edge: the gem/post-state that triggered this one |

## Typed body — `decision`

- `action` — typed descriptor: `{name, args}` (near-PDDL; bind variables later).
- `reasoning` — the trace, the *why*. **The most underrated field.** It is what
  lets credit be *extrapolated* past sampled support: predict X works on unseen
  Z by checking whether Z carries the feature X broke on. Write *why*, and *which
  feature* it would fail on.
- `tests[]` — bound verifier(s): `{id, how_to_run, what_counts}`. Success is
  meaningless unbound.
- `pre` — precondition predicate (extracted; the canonical pre→post is the git
  diff `parent → self`).

## Typed body — `knowledge` (a fact is a decision whose action is belief revision)

- `pre` = "did not hold belief X"; `action` = the epistemic update;
  `belief` = "believe X"; `credence` = storage-time confidence;
  `tests[]` = the justification / source check.
- A fact is worth its **track record**, not its storage-time credence
  ("used in 12, vindicated in 9"). That number is the consolidation signal.

## Typed body — `observation`

- Raw sensor/tool output incited by a decision. Minimal: `content`,
  `consumed`/`incited_by` set, no `test` required.

## On disk (one commit per gem)

```
gem/
├── meta.json     # envelope: kind, provenance, cost, reversibility, consumed[], incited_by
├── body.json     # typed body: action descriptor, test spec, structured fields
├── reasoning.md  # the trace / why  (grep-friendly; the extrapolation field)
├── pre.json      # precondition predicate (the matchable form)
└── index.json    # index_keys: precondition_shape, action_type, domain, test_ids
```

`success` is **not** in the commit — it is mutable valuation and lives in a git
note (`refs/notes/success`). Credit lives in `refs/notes/credit`. The commit is
immutable; valuation is append-only. **Immutable decision, mutable valuation.**

## Three-valued success (do not collapse)

Every success cell is `pending` (⊥, never judged) or a signed score in [-1, +1].

- `pending` ≠ failed. A fresh bet starts ⊥.
- `0.0` = present but inert.
- negative = present and harmful.

Collapsing ⊥ into 0 or "false" poisons everything downstream.

## Minimal capture spec (JSON)

```json
{
  "kind": "decision",
  "actor": "claude",
  "session": "sess-2026-06-30",
  "action": {"name": "retry_with_backoff", "args": {"max": 5}},
  "reasoning": "Transient 503s under failover; idempotent upsert is safe to retry. Would break if the op were non-idempotent.",
  "tests": [{"id": "t_failover", "how_to_run": "pytest -k failover", "what_counts": "no lost writes"}],
  "pre": {"error_class": "transient", "idempotent": true},
  "precondition_shape": ["transient", "idempotent", "retry", "backoff"],
  "action_type": "retry_backoff",
  "domain": ["database"],
  "reversibility": "reversible",
  "consumed": []
}
```
