---
name: gemmery
description: >-
  Capture and retrieve durable agent memory as a versioned git DAG with earned,
  test-bound credit. Use whenever the agent makes a non-trivial decision worth
  recording, wants to recall how a similar problem was solved, needs to browse
  past reasoning (including abandoned attempts), or asks "have we done something
  like this before" — and whenever a task completes successfully and stored
  knowledge should be credited. Prefer this over ad-hoc notes or flat vector
  recall for any multi-step task where prior decisions, their preconditions, and
  what actually worked matter.
---

# Gemmery — versioned agent memory with earned credit

Gemmery stores decisions and knowledge as an immutable, branchable git DAG. Each
record is a **gem**. Capture and retrieval are **intentional actions you take**,
not a background hook — your *choice* to record is itself signal.

> **Status gate.** Only capture + browse are live. Credit (§7) and operator
> promotion (§8) are **gated** behind a replicated Phase-0 result and will error
> if invoked. Do not pretend they work. See `references/credit-and-operators.md`.

## When to capture (a judgement call — that judgement is signal)

- After a **decision with a checkable outcome** (you can name a test).
- When acquiring a **fact** worth its future track record (not its storage-time
  confidence).
- **Not** for trivial mechanical steps. Capturing everything is noise.

## How to capture

Read `references/schema.md` first. Then fill the spec and run:

```bash
python scripts/capture.py spec.json        # or: echo '{...}' | scripts/capture.py -
```

Get these right — the rest of the system depends on them:

- **Give the gem a home (`--path`).** The memory is a real file system: every
  commit's tree is the whole store at that moment. Choose a meaningful path
  (`knowledge/tells/P2`, `decisions/2026-07-01/retry-choice`, `history/P2/game-12`)
  — the path is part of the note-keeping. For an **evolving** note (a dossier, a
  profile, a running belief), keep the path stable and use `--revise`: the new
  version replaces the old at HEAD, every prior version stays in history
  (`gemmery history <path>`), and the revision automatically `consumes` its
  predecessor so credit lineage follows.
- **Write real notes, not one-liners.** `reasoning.md` should carry the why,
  the evidence base, known failure modes, and *what would change your mind* —
  it is the field credit extrapolates from and future-you recognizes with.
- **Bind a `test`.** Success is meaningless unbound. `{test_id → score}`, signed
  in [-1, +1]; a fresh gem's success is `pending` (⊥), *not* failed.
- **Record `consumed[]` honestly** — the sha[] of gems this one used. Credit
  flows backward along these edges; an omitted edge is lost credit.
- **Set `reversibility_class`** (`pure` / `reversible` / `compensable` /
  `irreversible`). Git rewinds your epistemic state, not the world.
- **Index on solution shape**, not just the problem: fill `precondition_shape`
  and `action_type` with method-level tokens. This is what makes a method
  findable from a *differently-worded* future problem.

## When and how to browse (recognition, not one-shot recall)

```bash
python scripts/browse.py "how did we handle transient retries" --budget 8
```

The memory is also directly browsable as files — often the fastest first move:

```bash
gemmery ls -R                      # the whole memory tree
gemmery cat knowledge/tells/P2/reasoning.md
gemmery history knowledge/tells/P2 # every version of an evolving note
gemmery ls --sha <sha>             # the memory as it was at any past commit
```

Read `references/browse-patterns.md` before nontrivial retrieval. The loop:

1. **Reformulate** into several surface forms — problem-side *and*
   solution-side. Don't compare one cosine.
2. **Pre-filter on handles, then read.** Filter columnar (action type,
   precondition shape, outcome tag, credit) before semantic search. Never
   semantic-search the whole store cold.
3. **Recognize, don't expect recall.** You won't retrieve the right gem by
   similarity; you'll *recognize* it as applicable when you read it across a few
   queries.
4. **Walk the topology.** Pickaxe across diffs, filter by outcome tag, traverse
   the frontier (`main..frontier/*`), diff two world-states. A flat vector store
   can't do this; the git graph is why the substrate earns its place.

## Selection over merge

Belief states don't three-way-merge like code. Explore branches, score, and
**cherry-pick the winner to `main`**; leave the frontier intact for later
synthesis. `main` is canonical accepted history; `frontier/*` is speculative.

## Capture after success

When a task completes and stored knowledge was load-bearing, attach a signed
success to the gems that helped:

```bash
python scripts/browse.py ...                 # find what you used
gemmery success <sha> <test_id> <score>      # signed in [-1, +1]
```

(Backward credit *propagation* along `consumed[]` is the gated Phase-1 feature;
attaching per-test success to a gem is live now.)

## Pointers

- `references/schema.md` — the gem schema. Read before first capture.
- `references/browse-patterns.md` — reformulation + topology-walk patterns.
- `references/credit-and-operators.md` — §7-8 detail; only relevant once the
  Phase-0 gate clears.
