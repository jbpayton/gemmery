# What is actually in Git — the good case (with the post-hoc explainer)

A real Gemmery `GitStore` (regenerate with
`python experiments/integrated/show_whats_in_git.py`). It captures ONE planning
decision end to end, and — because every state is an immutable commit and
valuation is append-only — the whole thing is **traversable after the fact**.

## 1. The DAG

```
* 5ee15e1 (HEAD -> main, tag: ok/plan_success/5ee15e1b4fdb) decision: rely_on_advisor
| * d5d504e (frontier/plan/A_noise/0) decision: rely_on_advisor
|/  
| * e21d2d4 (frontier/plan/A_fallen/0) decision: rely_on_advisor
|/  
| * f636331 (frontier/plan/A_good/0) decision: rely_on_advisor
|/  
| * 49b1b60 (frontier/plan/A_now/0) decision: rely_on_advisor
|/  
* fe43baf knowledge: open_decision
* 97c5b98 knowledge: reliability_observation
* c7fde8d knowledge: reliability_observation
* 61f3134 knowledge: reliability_observation
* fbd722a knowledge: recency_reliability
* fe2bfa4 knowledge: recency_reliability
* 30de5ca knowledge: recency_reliability
* d711129 knowledge: recency_reliability
```

`main` = evidence gems the planner consulted, the decision point, and the
selected plan (cherry-picked). Each `frontier/plan/*` branch is one hypothesis.

## 2. Refs (branches, outcome tag, note refs)

```
refs/heads/frontier/plan/A_fallen/0
refs/heads/frontier/plan/A_good/0
refs/heads/frontier/plan/A_noise/0
refs/heads/frontier/plan/A_now/0
refs/heads/main
refs/notes/credit
refs/notes/deps
refs/notes/success
refs/tags/ok/plan_success/5ee15e1b4fdb
```

## 3. A gem on disk (`main:gem/meta.json`) — note `consumed`

```json
{
  "consumed": [
    "d71112938000e348ec1cfebfe44133c401682566"
  ],
  "cost": {
    "tokens": 0,
    "tool_calls": 0,
    "wall_time_s": 0.0
  },
  "incited_by": null,
  "kind": "decision",
  "provenance": {
    "actor": "planner",
    "session_id": "sess-2026-07-01",
    "signed": false,
    "timestamp": 1700000030
  },
  "reversibility_class": "pure"
}
```

`reasoning.md` (the *why*):

```
Hypothesis: rely on A_now. Simulated plan value = its current reliability 0.89 (see consumed evidence). currently the most reliable (recent record).
```

## 4. Valuation notes on the selected gem (folded)

```json
{
  "success": {
    "plan_success": 1.0
  },
  "credit": {
    "total": 0.497,
    "n_events": 1,
    "by_source": {
      "49b1b60b3fe5d562d5e059edf3df43b2892fe4ff": 0.497
    }
  }
}
```

---

# Git as a post-hoc explainer

The question "why was this hypothesis made?" is answerable *entirely from the
repository*, after the fact:

**(a) Why was `rely_on(A_now)` chosen?** Walk the selected plan's `consumed`
edge → the evidence gem it rested on:

```
selected plan 5ee15e1b4f  --consumed-->  evidence d711129380
  "Evidence: recency-filtered reliability of A_now = 0.89 (git query over the recent window). currently the most reliable (recent record)."
```

and the alternatives are still on their `frontier/plan/*` branches, so you can
see *what else was considered and why it lost*:

```
  rely_on(A_now): value 0.89  <-- SELECTED
  rely_on(A_good): value 0.80
  rely_on(A_fallen): value 0.38
  rely_on(A_noise): value 0.33
```

`A_now` had the highest simulated value → selected. Nothing was discarded; the
losing hypotheses remain, each with its own `consumed` evidence.

**(b) The whole memory state is traversable over time.** `A_fallen` was once
trustworthy and has decayed — and that history is walkable:

```
    Observation (1yr ago): A_fallen's reliability measured at 0.85.
    Observation (6mo ago): A_fallen's reliability measured at 0.55.
    Observation (now): A_fallen's reliability measured at 0.38.
```

The planner consumed the **recent** reliability (0.38), so it correctly
distrusted `A_fallen`. A flat notes file read from the top would have seen only
the stale 0.85 and been fooled — the failure mode from the integrated test. Here
you can *prove* which value the decision used (`git show
5ee15e1b4f` and its consumed edge) and reconstruct the exact memory as of any
commit (`git checkout <sha>`; `git show <sha>:gem/...`).

**(c) Valuation history is preserved too.** Credit and success are append-only
notes, so `git log refs/notes/credit` replays how a belief's value evolved — you
can see not just *what* is believed now but *how it came to be*.

## Why a flat/overwritten store can't do this

A markdown scratchpad that is edited in place, or a vector index that is mutated,
keeps only the *current* state. Git keeps *every* state plus the dependency edges
and the append-only valuation, so the causal trace — what was known, what it
rested on, and why a choice looked best at the time — is fully recoverable. That
is auditability and post-hoc explanation as a property of the substrate, not an
add-on.
