# SWE living-repo experiment — 12 chronological Django ORM issues (2020)

The original spec's target domain (§10.2), re-entered with the headroom rule.
Setup: 12 consecutive db-subsystem issues from SWE-bench Verified, solved in
time order at their true base commits (git worktrees). Fault-localization
scoring vs the gold patch's files (recall@5, top-1). Arms: **fresh** (cold every
issue) vs **memory** (a store of dossiers the agent itself writes — a solve
agent that reads them + a librarian that, after each reveal, decides what is
durably worth remembering). First-ever test of **Invariant 5: intentional
capture**.

## Accuracy (n=12)

| arm | recall@5 | top-1 |
|---|---|---|
| fresh | 1.000 | 0.917 |
| **memory** | 1.000 | **1.000** |

Both arms at recall ceiling — SWE-bench django issues are effectively memorized
(the contamination we predicted). The single point of headroom was issue 11
(`Random` expression in GROUP BY), where fresh mis-ranked and **the memory arm
got it right by explicitly applying a librarian-distilled rule** ("fix where the
state is produced, not at the consumer") against the reporter's suggested
compiler-side fix. n=1 — mechanistically attributable, not statistically
meaningful alone.

## Cost (the honest line)

| | per-solve tokens | tools | total |
|---|---|---|---|
| fresh | 15.0K | 5.8 | 181K |
| memory (solve) | 24.0K | 6.9 | 288K |
| + librarian | 19.1K/issue | 4.1 | 210K |
| **memory arm total** | | | **498K (2.8×)** |

On an at-ceiling repo, memory bought +1 top-1 for 2.8× cost. The economics
invert only where headroom is real (post-cutoff repos, harder localization,
actual patch generation) — consistent with every headroom result in this series.

## The real product: the intentional-capture record (Invariant 5 works)

Across 12 issues the librarian: captured **9 dossiers** (never dumping — ~1 per
issue, several issues judged "nothing durable"); **revised the same dossier 3
times**, each revision *narrowing its rule against a falsifying case* (the
"multi-file backend fix" rule acquired scope-checks: operations.py-dispatch vs
vendored `as_<vendor>` vs correct-consumer-of-bad-value); recorded
**counterpoints to its own earlier rules**; and cross-referenced dossiers. The
solve agents then *cited these rules by name* ("fix-where-the-reference-is-
constructed", "single construction point") and applied them to new bugs — 
within-repo method transfer through agent-written memory, the mechanism the
original spec bet on, observable in the store's revision history.

A theory of Django's backend-dispatch architecture literally crystallized in
`knowledge/` over three months of 2020 ORM issues — formed, falsified, scoped,
confirmed twice. Browse it: `experiments/swe/browser.html`.
