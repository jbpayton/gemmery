# The evidence behind Gemmery

Every design default in Gemmery traces back to an experiment in
[`experiments/`](experiments/), each with its own `RESULTS.md` and the exact
scripts that produced its numbers. This document is the connected scorecard:
what was tested, what won, and — just as load-bearing — what lost.

A note on words used throughout: an **arm** is one configuration under test
(e.g. "with memory" vs "without"); **headroom** is the gap between what the
model does cold and what the task needs; scores are **accuracy** unless
another metric is named.

## Question 1 — Does memory *content* help at all?

Memory can only help when it carries information the model lacks.

| regime | does memory help? | evidence |
|---|---|---|
| Solve a task the model already solves cold | **No** (Δ≈0.00) | [`v2_solve_pilot`](experiments/v2_solve_pilot/RESULTS.md) — a strong model solves textbook tasks unaided and *discards* weaker hints |
| Recall/transfer a method across differently-worded problems | Retrieval works | [`transfer_recall`](experiments/transfer_recall/RESULTS.md) — agentic query reformulation lifted recall 0.79 → 1.00 |
| Experiential knowledge ("read this opponent") | **Yes, large** | [`werewolf`](experiments/werewolf/RESULTS.md) — in a social-deduction game, memory of an opponent's behavioral tells scored 1.00 vs 0.36 cold |

The value of memory concentrates exactly where the model is *ignorant*:
experiential facts, opponent behavior, project-specific knowledge — not
general competence it already has.

## Question 2 — *Given* that memory helps, which storage layer serves the query?

No single substrate wins everywhere — the right retrieval depends on the
query. Full matrix with every cell measured:
[`experiments/summary_matrix.png`](experiments/summary_matrix.png); numbers
from [`scale`](experiments/scale/RESULTS.md),
[`complex_rules`](experiments/complex_rules/RESULTS.md), and the game
experiments.

| query type | no memory | flat file (read/grep) | vector (embeddings) | structured (columnar) | **Gemmery (both)** |
|---|---|---|---|---|---|
| small memory (fits in context) | 0.36 | 1.00 | 1.00 | 1.00 | **1.00** |
| rare existence ("did X ever happen?") | 0.45 | 0.53 | 1.00 | 1.00 | **1.00** |
| exact aggregate over a dense set ("who most / how often?") | 0.50 | 0.43 | 0.57 | **1.00** | **1.00** |
| complex noisy rule ("what will they do here?") | 0.50 | 0.50 | **0.78** | 0.61 | **0.78** |

Reading the rows:

- **Small memory:** a flat markdown scratchpad *ties* everything — while
  memory fits in context, structure buys efficiency and provenance, not
  accuracy.
- **Rare existence:** reading everything fails at scale, but vector search
  over a flat file matches the structured index — the needle is a
  near-duplicate of the query, so structure is *not* required here.
- **Exact aggregates:** vector top-k retrieval is only a sample and cannot
  count; only the columnar index is exact. Credit — a signed total over a
  record's outcome history — is exactly this kind of query, which is why a
  vector store alone cannot provide it.
- **Complex noisy rules:** the exact matching cell is empty in a
  high-dimensional situation space, so structured lookup starves; only
  similarity retrieval generalizes.

**Vector and columnar are complementary opposites** — one generalizes across
sparse experience, the other computes exact totals over dense sets. Gemmery
carries both over one immutable record and uses whichever the query needs.
(An earlier draft of this project claimed "structure always wins"; the
matrix corrected it.)

## Value off the accuracy axis

Two properties never show up as an accuracy number, by nature:

- **Auditability and provenance:** immutable records, signed authorship, an
  append-only valuation history. A flat notes file can be silently
  rewritten; the git record cannot.
- **Branching, selection, rewind:** explore alternatives on branches,
  cherry-pick winners onto `main`, reconstruct exactly what was believed at
  any commit. Coordination and reproducibility, not recall.

---

# Part II — dynamics, real data, and other agents

The matrix above answers static questions. The experiments below add time,
noise, money, and multiple writers.

## When the world changes, revise — don't hoard ([`drift`](experiments/drift/RESULTS.md))

Setup: an opponent's behavioral rules change partway through play. Beliefs
built from all-history counts *dilute* the change and keep answering from
the old world; beliefs revised at a stable path (or decayed) track it. This
is the query type where the versioned store is required rather than merely
tied: a flat log cannot distinguish "was true" from "is true."

## Simulation pays only past a horizon, and only with a good model ([`simulate`](experiments/simulate/RESULTS.md), [`futures`](experiments/futures/RESULTS.md), [`futures_eval`](experiments/futures_eval/RESULTS.md))

Setup: an agent that can roll its belief network forward before acting.
Look-ahead beat act-now only when consequences were several steps deep —
below that horizon, simulating was pure cost. And fidelity gates everything:
an agent that faithfully simulated a *miscalibrated* world model did worse
than one with no memory at all. The sharpest version appeared in gameplay
where the world's rules had to be *inferred from past game records*: an
agent reasoning casually over those records inferred a plausible-but-wrong
rule and fell for every one of 8 planted traps (0/8), while an agent that
fitted candidate rule-sets to the records, kept only the survivors, and
rolled each forward as an explicit branch scored optimally (12/12).

## Retention compounds ([`reuse`](experiments/reuse/RESULTS.md))

Setup: 60 rounds against recurring situations, with the opponent's rule
changing at round 30. An agent that kept its records reached ~0.98 of the
optimal score by late game; a no-retention baseline stayed flat at its
starting level. After the rule change, dropping the oldest records until
the survivors were consistent again ("windowed refit") recovered within a
few rounds — and previously computed look-ahead branches were reused as a
plan cache whenever they were still valid.

## Real markets: the edge is robustness, not prophecy ([`market`](experiments/market/RESULTS.md))

Setup: predict next-day stock movement from prices and news, walk-forward
(no future data), on the StockNet benchmark (88 tickers, 2014–16) and then
FNSPID (13 years of financial news). Signal dossiers — per-signal track
records, credit-weighted — beat both no-memory and a recency log by +0.036
MCC (Matthews correlation, a chance-corrected accuracy for imbalanced
classes), replicating in 13 of 14 years (p≈0.0009). Only trading when the
dossier was confident raised MCC by +0.10 while acting on 30% of days. A
planner doing look-ahead over memory-fitted dynamics kept its performance
as simulated trading costs rose, while the act-on-today's-signal policy
collapsed — simulation's measurable job was surviving friction, not seeing
the future. The presentation lesson: when memory was injected as *numbers*
(counts, rates), the model computed with it in 60 of 60 trials; injected as
prose, the model overrode it with its own priors.

## Software engineering: intentional capture works ([`swe`](experiments/swe/RESULTS.md))

Setup: 12 real Django issues solved in chronological order at their true
historical commits, with a librarian distilling each session. The memory
arm localized the correct file first-try 12/12 vs 11/12 fresh — the win
came from citing a librarian-written rule by name ("fix where the state is
produced, not at the consumer") against a misleading suggestion in the
issue text. The capture record was the deeper result: roughly one dossier
per issue (selectivity held), and one dossier revised five times, each
version narrowing its rule against a case that falsified the previous one.
Cost, honestly: 2.8× tokens on a benchmark the model had largely memorized
— memory pays at the margin, where headroom exists.

## The external ladder: LongMemEval ([`lme`](experiments/lme/RESULTS.md))

Setup: [LongMemEval](https://github.com/xiaowu0162/LongMemEval) asks
questions about a user's ~50 past chat sessions (~115K tokens). We ran a
60-question stratified sample under the standard LLM-judge protocol, four
ways:

| arm | approach | accuracy |
|---|---|---|
| v1 | cosine retrieval over truncated turns | 0.733 |
| **v2** | reranked whole-session retrieval over the raw record | **0.917** |
| v3.0 | LLM summarizes everything at write time (50× compression) | 0.367 |
| v3.1 | same, with a much larger summary budget (23×) | 0.500 |

**The raw record beats a bad summary.** A question-blind summarizer cannot
know which incidental detail a future question will hinge on. Its failures
were honest omissions — in 32 of 38 misses the answer was "I don't know" —
and on the 8 questions per run designed to be unanswerable, all four arms
abstained correctly on all 8. Combined with the SWE result, this fixed the
production rule: **distill judgment, retrieve facts.**

## Multiple agents: conflicts are where the information is ([`multi`](experiments/multi/RESULTS.md))

Setup: four agents with unequal, *unknown* observation reliabilities
investigate 90 hidden facts; after each team answer the truth is revealed
and each agent's track record updates. Sharing memory through a single
last-write-wins slot per fact — what a communal notes file is — scored
*below* not sharing at all (0.725 vs 0.881), because a late write from an
unreliable agent silently replaces a reliable one. With each agent writing
to its own branch, disagreements surfaced explicitly, and conflicts
resolved by earned credit, the team scored 0.984 — statistically at the
0.988 ceiling of an adjudicator that knows the true reliabilities. On
unanimous questions all methods tied exactly: every point of the win came
from the 54% of questions where perspectives disagreed. The same game
replayed on the real store (branch per agent, winners selected onto
`main`, losers still readable on their branches) matched the simulation's
answers exactly, 86/86.

## From findings to product ([`tools/prod/README.md`](tools/prod/README.md))

The laws above are the production defaults: `gemmery init` wires
session-start injection (numbers lead), a zero-LLM outcome ledger, and a
session-end librarian (selective capture, revision-first, failures debit
2×). Hardening was measured at 100,000 gems: capture flat at ~3ms, zero
loss under 4-process concurrency, secrets redacted before storage, history
reads 25× faster through a rebuildable cache.

**Bottom line:** memory helps where the model is ignorant and only there;
keep the raw record and retrieve it well; distill judgment, not facts; date
and revise beliefs instead of accumulating them; surface disagreement and
let track records settle it; and make every stored claim payable by a test.
The one question these experiments could not settle — whether credit still
accrues useful signal when outcomes arrive late, messy, or never — is now
running as a live experiment: this repository develops Gemmery with Gemmery.
