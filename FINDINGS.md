# Gemmery — where every memory approach lands, in the end

This is the scorecard for the whole investigation: a string of increasingly
pointed experiments (each in `experiments/`, each with its own `RESULTS.md`),
built to *falsify* the value of versioned agent memory as cheaply as possible.
Two separate questions fell out, and conflating them is the usual mistake.

## Question 1 — Does memory *content* help at all? (headroom)

Memory can only help when it carries information the model lacks.

| regime | does memory help? | evidence |
|---|---|---|
| Solve a task the model already solves cold | **No** (Δ≈0.00) | `v2_solve_pilot` — a strong model solves textbook tasks unaided and *discards* weaker hints |
| Recall/transfer a method across surfaces | Retrieval works | `transfer_recall` — browse reformulation recall 0.79 → 1.00 |
| Adversarial / experiential ("read this opponent") | **Yes, large** (+0.64) | `werewolf` — memory of tells 1.00 vs cold 0.36 |

So the value of memory is concentrated exactly where the model is *ignorant*:
experiential facts, opponent behavior, project-specific knowledge — not general
competence it already has.

## Question 2 — *Given* memory helps, which substrate serves the query?

No single substrate wins everywhere — **the right retrieval depends on the query**
(`summary_matrix.png`, numbers measured in the experiments):

| query type | no memory | flat file (read/grep) | vector (embeddings) | structured (columnar) | **Gemmery (both)** |
|---|---|---|---|---|---|
| small memory (fits in context) | 0.36 | 1.00 | 1.00 | 1.00 | **1.00** |
| rare existence ("did X ever happen?") | 0.45 | 0.53 | 1.00 | 1.00 | **1.00** |
| exact aggregate over a dense set ("who most / how often?") | 0.50 | 0.43 | 0.57 | **1.00** | **1.00** |
| complex noisy rule ("what will they do here?") | 0.50 | 0.50 | **0.78** | 0.61 | **0.78** |

Reading the rows:

- **Small memory (fits in context):** a flat markdown scratchpad *ties* everything
  — structure buys nothing on accuracy, only efficiency/provenance
  (`werewolf`, `gnosia`).
- **Rare existence:** read-it-all fails at scale, but **vector RAG over the flat
  file matches the structured index** — the needle is a near-duplicate of the
  query (`scale/vector_demo`). Structure is *not* required here.
- **Exact aggregate over a dense set:** vector top-k is only a sample and can't
  count; **only the structured columnar index is exact** (`scale/vector_demo`).
  This is exactly what earned **credit** (§7) is — a signed aggregate over the DAG.
- **Complex noisy rule:** the exact conditional cell is empty in a high-dim
  situation space, so structured lookup starves; **only similarity retrieval
  generalizes** (`complex_rules`). The mirror of the row above.

**Vector and columnar are complementary opposites** — one generalizes across a
sparse high-dimensional space, the other computes exact totals over dense sets.
The `Gemmery` column is the only one high on *every* row, because it carries
**both** an embedding index and a columnar index over one immutable DAG and uses
whichever the query needs. A pure-markdown store (text/vector only) or a pure-SQL
store (exact only) each cover one row and miss another. That — not "structure
always wins" (a claim an earlier draft overreached on and this repo corrects) —
is the defensible case for the two-layer design.

## The third axis — value that isn't accuracy

Two of Gemmery's properties never showed up as an accuracy number and never will,
because they aren't about accuracy:

- **Auditability & provenance:** immutable records, signed authorship, an
  append-only valuation history ("used in 12, vindicated in 9"). A flat notes file
  can be silently rewritten; the DAG cannot.
- **Branching, selection, and rewind:** explore `frontier/*`, cherry-pick winners
  to `main`, rewind epistemic state. Coordination and reproducibility, not recall.

The original spec anticipated this: on accuracy at parity, ship Gemmery as an
**audit/coordination** system; the "smarter agent" claim only earns a green light
where memory is both load-bearing (Q1) and the substrate is decisive (Q2).

## Bottom line

- Memory helps when the model lacks the content — not for tasks it already does.
- For **retrieval / similarity**, a flat file + embeddings is as good as the index.
- The structured index is uniquely necessary for **exact aggregation** (which is
  what credit is); similarity is uniquely necessary for **generalizing a complex
  rule**. Gemmery is the only substrate here that does both.
- Everything else Gemmery offers — audit, provenance, branching, credit — is real
  value that lives off the accuracy axis entirely.

Every number above is reproducible from the scripts in `experiments/`; see each
subfolder's `RESULTS.md`.
