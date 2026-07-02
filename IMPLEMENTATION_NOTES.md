# Implementation notes — Gemmery v0.1

What was built, the decisions behind it, and (honestly) what it does and does not
yet show. Maps to the spec by section.

## What's built (spec §14.1–§14.5)

- **`store/`** — git-native capture/read. pygit2 builds the gem tree in memory
  and commits with no working-tree writes; notes (success/credit/deps) are
  written via pygit2; pickaxe / `--grep` / tag globs / frontier diffs go through
  subprocess git. **Capture median ~2 ms** (invariant: < 25 ms, §1.9).
- **`index/`** — SQLite columnar pre-filter + an embedding layer over
  `reasoning` and **precondition-shape**. `rebuild()` reconstructs both from git
  alone and asserts parity (`indexed == commits`, §1.6). Hybrid retrieve enforces
  the contract: columnar/lexical pre-filter **then** semantic — never cold.
- **`browse/`** — the bounded loop (§6.1) with an exact model-call budget, a
  membrane permeability knob (sealed default, §6.2), topology-walk tools, and
  pluggable policies (`MockPolicy` offline; `AnthropicPolicy` for real runs).
- **`eval/`** — Phase 0: the dataset + decorrelation analysis (§10.2), the three
  arms with matched-compute logging (§10.1/§10.4), pre-registration-as-commits
  (§10.3), and the exploratory→confirmatory replication runner.
- **`skill/`** — `SKILL.md` (+ pushy description), `scripts/` (thin wrappers over
  one CLI engine), `references/`, `evals/`.
- **`credit/` `operators/` `effects/`** — documented, gated stubs that raise with
  the gate reason.

## Key design decisions

- **The store is an accumulating file system (v0.2 fix).** Originally each
  commit's tree held *only* the gem being captured — a ledger, not a filesystem —
  which broke the spec's own idea that post-state IS the commit tree and the
  effect IS `git diff parent self` (§2.1), and made `git checkout` useless for
  state reconstruction. Fixed: `capture(gem, path=...)` inserts the gem's five
  files into the parent's tree at a meaningful path (`knowledge/tells/P2`,
  `decisions/round1`, default `<kind>/<ts>-<action>`), recorded as a `Gem-Path`
  trailer. Now every commit's tree is the whole memory as of that moment
  (`ls`/`read_file`/`tree_listing`/checkout all real), a gem's effect is exactly
  its diff, paths never silently shadow (auto-uniquify), and `select_to_main`
  cherry-picks *only the winner's subtree* — never the frontier's whole state.

- **Notes as append-only JSONL, folded to a value.** Git notes normally replace.
  We instead append valuation *events* and compute the current value as a fold,
  so the valuation *history* ("used in 12, vindicated in 9", §7.3) is auditable —
  not just the latest number. Immutable decision, mutable-but-auditable valuation.
- **Gem-space excludes `refs/notes/*`.** All gem walks use `--branches --tags`, so
  notes-commits never leak into retrieval or the parity count. (This was a real
  bug caught by the index parity test.)
- **PENDING is a sentinel that refuses truthiness.** `bool(PENDING)` raises, so
  three-valued success can't silently collapse to false (§1.3).
- **Model calls are the budgeted resource, not loop iterations.** The control
  arm's honesty depends on counting the *expensive* thing (reformulate + assess +
  solve). The budget is a hard ceiling; arm 1 and arm 3 run the identical loop so
  their compute matches by construction.
- **Selection-over-merge** is implemented as `select_to_main` re-committing a
  winning gem's tree onto `main` (the frontier gem stays immutable).

## The honest finding from the offline baseline

The harness is wired to be **falsifiable**, and the offline default already
exercises that:

- With the dependency-free `HashingEmbedder` + the deterministic `MockPolicy`,
  **browsing does not clearly beat one-shot retrieval at recognition** — the
  mock browser's selectivity actually surfaces *fewer* transfer gems than a
  single top-k lookup (`arm2.recognition_rate > arm1.recognition_rate` at the
  same gain). And `one_shot+memory` with its freed budget spent on extra solve
  attempts scores very high **even at `transfer_gain = 0`** — a textbook
  relabeled-compute artifact (§10.4). This is the GitOfThoughts null reproduced
  by a weak agent.
- The green-light path is reachable only when a *capable* browser recognizes
  genuine cross-surface transfer. The `SimulatedSolver(transfer_gain)` knob lets
  the test suite assert both outcomes: gain 0 → no green light; gain high →
  replicated green.

**Conclusion the code already supports:** a weak browsing agent doesn't escape
the null. The escape, if it exists, requires the real ingredients below — which
is exactly the scientific posture the spec demands (the burden is on memory).

## A real-agent result that supports the mechanism (transfer-recall experiment)

Run with real Claude sub-agents as the reformulation policy + real
sentence-transformer embeddings (`experiments/transfer_recall/`, committed
fixture; `RESULTS.md`):

| transfer recall@5 | one-shot | browse (MockPolicy) | browse (Claude reformulation) |
|---|---|---|---|
| real embeddings | 0.79 | 0.25 | **1.00** |
| hashing | 0.50 | 0.25 | **0.96** |

A real agent's solution-shape reformulations **recovered every transfer gem
one-shot missed** (the memoize/accumulator-across-distant-surfaces cell) with no
regressions. This is the escape mechanism working at the *retrieval* layer — and
it pinpoints `MockPolicy` (0.25), not retrieval, as what made the offline harness
look null. **Caveat, load-bearing:** this is recall, not solve accuracy; n=24,
single run, not pre-registered. It earns the right to run the end-to-end efficacy
experiment; it does not substitute for it. No API key was needed — the "model in
the loop" was Claude sub-agents.

## What a real efficacy run needs (before trusting any green light)

1. **Real embeddings** — install `gemmery[embed]`; swap `SentenceTransformerEmbedder`
   into `GemIndex`/`decorrelation_report`. Re-run the decorrelation report with
   the *pinned eval embedder* (the AUC≈1.0 here is a construction artifact, see
   `dataset.py:construction_note`).
2. **A real browsing agent** — install `gemmery[llm]`; use `AnthropicPolicy`
   (pin `claude-opus-4-8`) and `AnthropicSolver` with real verifier execution.
   **Sandbox** `run_verifier` (subprocess + rlimits/container) before running
   model-written code.
3. **A real dataset** — the 24-task seed proves the *construction is possible*;
   an honest run needs more tasks (for power: GitOfThoughts died from n=40 to
   n=98) and human-authored solution references rather than shared templates.
4. **Finalize the pre-registration** before the first real run (`default_prereg`
   is a draft) and commit it.

## v2 task set — open-ended, objective-scored (`gemmery/eval/tasks_v2.py`)

The v1 seed set was over-constrained (it named the technique → one solution →
solvable cold → no headroom for memory, and "transfer" = recognize a textbook
pattern = answer-copying). v2 fixes the *task shape*:

- **16 tasks across 4 families** — heuristic/strategy design, optimization,
  behavioral/property design, debug/feature — each a transferable *approach*
  instantiated across surface-dissimilar domains.
- **Verified by an objective, not an exact output.** Every task has a
  `ScoredVerifier` that runs the candidate against seeded instances and returns a
  continuous score; there is a real design space, and "better vs worse" is what's
  measured (Invariant 2). Determinism: optimization tasks score by *element-access
  count*, not flaky wall-clock.
- **Discrimination gate.** Every approach ships a strong `reference_solution`
  (clears the threshold) and a plausible `naive_solution` (must not).
  `validate_discrimination` asserts the verifier separates them — the per-task
  analogue of the kill-switch. It already caught a bad knapsack verifier (naive
  ≈ reference) and a short-circuit bug in a reference parser.
- **Narrative ≠ contract.** Each task's `problem_text` is the surface situation
  only (no technique, no API); the API spec lives in `contract`. Diversifying the
  same-approach narratives dropped surface↔method correlation from r=0.83 (not
  feasible) to r=0.33 (feasible): the transfer cell is isolable.

**The decisive finding:** on v2 the deterministic `MockPolicy` browser's
recognition rate is **0.00** (vs 0.25 on v1), so the harness refuses even at
`transfer_gain=0.7`. Making the surfaces method-agnostic *defeats the cheap
token-matching baseline* — which is the whole point. v2 cannot be gamed by
answer-copying; it requires a real reasoning agent that reformulates toward
solution shape. Run it: `python -m gemmery.eval.run_phase0 --dataset v2`.

## v2 end-to-end solve pilot — a clean, useful null (`experiments/v2_solve_pilot/`)

Ten Claude sub-agents solved the 16 v2 tasks WITH the transferable approach in
context vs COLD (matched calls; the arm1-vs-arm3 comparison). Result:
**Δ = +0.000, both arms 16/16 at a perfect mean score of 1.00.** Not noise —
two mechanisms, both in the agents' own notes:

1. **No headroom.** The cold agents independently reached for the strong/optimal
   approach on every task (DP knapsack, LPT + branch-and-bound *beating* the
   reference LPT, sliding-window limiter, prefix sums, hash-set single-pass).
2. **Agents critique memory.** On knapsack/scheduling the memory-arm agents
   explicitly *rejected* the hint ("greedy is not optimal", "LPT is a 4/3
   approximation") and coded the exact optimum instead. Memory weaker than the
   model's own knowledge is discarded.

This reproduces the GitOfThoughts null at the *application* layer and sharpens it:
memory raises solve quality only when the model fails cold AND the stored
approach beats the model's unaided output AND the model recognizes it. None hold
here. So the binding constraint is **task-difficulty calibration**, not the
memory machinery — the next task set needs problems beyond the model's cold
competence where the stored approach is decisive. A concrete process upgrade this
implies: add a *model-relative* headroom gate (keep a task only if the cold
baseline scores well below ceiling), stricter than the existing
naive-vs-reference `validate_discrimination`. Full writeup + reproducer in
`experiments/v2_solve_pilot/RESULTS.md`.

## The efficacy arc (experiments/), in one place

Four rounds, each a cheaper falsification than the last:

1. **transfer_recall** — real-Claude reformulation recovers cross-surface
   transfer gems one-shot lookup misses (recall 0.79 → 1.00). Retrieval works.
2. **v2_solve_pilot** — open-ended objective-scored tasks: **clean null**
   (Δ=0.00). A strong model solves them cold and discards weak memory. Headroom,
   not machinery, is the constraint.
3. **werewolf + gnosia** (adversarial) — memory of opponents' tells is decisive
   (Werewolf +memory 1.00 vs cold 0.36). But a plain `.md` scratchpad **ties**
   Gemmery at both scales — memory *content* is load-bearing, its *structure* is
   not, as long as the whole history fits in context.
4. **scale** (beyond the context window) — decision hinges on a rare fact in an
   8M-token (~32 MB, 40× context) history. *Read-what-fits* collapses (LLM 0.50,
   det. 0.53). But the fair baseline is **vector search (RAG)** over the same
   markdown, and it **ties** the index on this rare-existence query (both 1.00;
   recall@50 = 40/40) — the needle is a near-duplicate of the query. So structure
   does *not* uniquely win at retrieval. Where it *does*: an **exact aggregate**
   over a large set ("who was the Gnosia most often?", close counts) — vector
   top-k is only a sample (0.57) and read-window worse (0.43); only the columnar
   `SUM/COUNT/GROUP BY` is exact (1.00).

**The synthesis (corrected after adding the vector baseline):**
- Memory *content* helps when the model lacks it (experiential / adversarial, or
  facts beyond training). Established.
- For *retrieval / existence / similarity*, **vector-RAG over a flat markdown file
  is as good as Gemmery's index** — structure is an efficiency + provenance win,
  not an accuracy one. (Read-it-all fails only because it can't hold the history;
  vector-RAG over that file is fine.)
- The one capability unique to the structured index is **exact aggregation over
  large sets** (counts, rates, ranking-by-total) — which no bounded read and no
  top-k retrieval can do. And that is precisely what **earned credit** (§7) is:
  a signed aggregate over the whole dependency DAG.
- The mirror case (**complex_rules**): predicting a person whose behavior follows
  a complex, noisy, high-dimensional rule is a *learning* problem, and there
  **similarity retrieval (kNN/embedding) wins and exact conditional aggregation
  starves** (the exact current-situation cell is almost always empty). kNN 0.78
  vs exact-cell 0.61 vs marginal 0.50 (Bayes 0.85). (Aside: an LLM reasoning over
  the retrieved neighbors *underperformed* a plain majority-vote of them — for
  noisy statistical prediction, retrieve-then-aggregate beats retrieve-then-reason.)

**Bottom line: no single substrate is best — the right retrieval depends on the
query.** Rare existence → vector ≈ index. Exact aggregate over a dense set →
only the columnar index. Complex sparse rule → only similarity. A store with
*both* an embedding index and a columnar index over one DAG (Gemmery) can serve
all three; a pure-markdown store (text/vector only) or a pure-SQL store (exact
only) each covers one. That — not "structure always wins" — is the defensible
case for the two-layer design.

## Known limitations / TODO

- `select_to_main` copies a single gem; multi-gem path selection (cherry-pick a
  sub-chain) isn't implemented.
- `-S` pickaxe only reports the *introduction* of a string; use `regex=True`
  (`-G`) to match any diff touching it (documented in browse-patterns).
- The embedding cache is loaded fully into memory — fine at eval scale, not for a
  very large store; a real deployment should page it or use `sqlite-vec`/Qdrant.
- Counterfactual credit, the training-data flywheel, and cross-agent merge are
  explicitly out of scope for v1 (spec §13).
