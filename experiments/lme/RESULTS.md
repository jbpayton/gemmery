# LongMemEval: Gemmery's first externally-comparable number

**v2: 0.917 overall (55/60)** — still zero LLM at ingestion. Mechanical
upgrades only (cross-encoder rerank, whole-session retrieval, CoT reader)
took v1's 0.733 into the vendor-leader bracket. See "v2" section below.

**v1: 0.733 overall (44/60)** on a stratified sample of LongMemEval_S
(cleaned), with **perfect abstention (8/8)** and **0.89 on knowledge-update**
— the two categories that map onto Gemmery's calibration and revision
machinery.

## Protocol

- **Dataset**: `longmemeval-cleaned/longmemeval_s` (500 questions; ~115K-token
  haystack of ~50 dated chat sessions each). Stratified sample of **60**
  questions across all six ability types (seeded, `build_lme.py`), abstention
  (`_abs`) questions force-included per type.
- **Ingestion — mechanical, zero LLM calls**: every turn becomes a dated memory
  record (`[date] (role): text`); MiniLM embeddings over turns (Gemmery's
  vector layer run in batch).
- **Retrieval**: top-15 turns per question by cosine, dates attached.
- **Reader**: Claude sub-agents, 10 questions per call, ~1.8K tokens of memory
  per question (**64× compression** vs the 115K-token haystack). Instructions:
  answer from memory; prefer latest-before-question-date; say exactly
  "I don't know" when memory is silent.
- **Judge**: LLM judge vs gold (standard LongMemEval protocol), 2 calls.
  Two reader-dropped `_abs` items were re-run and graded by the deterministic
  `_abs` rule (abstained = correct) — see `out/patch.json`.

## Results

| ability type | acc | n |
|---|---|---|
| knowledge-update | **0.89** | 9 |
| single-session-user | 0.88 | 8 |
| single-session-preference | 0.75 | 4 |
| temporal-reasoning | 0.69 | 16 |
| multi-session | 0.69 | 16 |
| single-session-assistant | 0.57 | 7 |
| **overall** | **0.733** | 60 |
| abstention subset (`_abs`) | **1.00** | 8 |

**Judge-free metric**: oracle retrieval recall@15 = **0.923** (48/52 answerable
questions had ≥1 evidence-session turn retrieved) — the ceiling the reader
plays under, measured before any LLM touched the data.

## Where this lands (published LongMemEval_S numbers)

| system | reported acc |
|---|---|
| full-context GPT-4o (paper baseline) | 60–64% |
| Mem0 | 49–67% (varies by eval) |
| Zep | 64–75% (varies by eval) |
| **Gemmery retrieval layer (this run)** | **73.3%** |
| Emergence AI RAG / ByteRover / Mastra | 86–95% (vendor-reported, heavy engineering) |

Honest caveats: n=60 sample (not the full 500); Claude reader (not GPT-4o);
our own LLM judge. Not a leaderboard submission — but the protocol matches the
published one and the number is in Zep's bracket, above full-context, from a
~40-line mechanical pipeline: no LLM at ingestion, no reranker, no query
decomposition, no session summaries.

## The mechanistic findings

1. **Retrieval misses become abstentions, not confabulations.** Of the 4
   answerable questions where the vector layer missed the evidence session,
   the reader said "I don't know" on 2 and confabulated on only 1. The system
   mostly knows when its memory is silent — the market abstention result
   (MCC +0.10 at 30% coverage) surfacing on an external benchmark.
2. **Perfect abstention (8/8)** — memory-not-present detection is free when
   the reader sees a *bounded, dated* memory instead of a 115K-token haystack:
   absence is legible in 15 snippets, invisible in 1,300.
3. **Knowledge-update 0.89** — dating every record and instructing
   latest-before-question-date is most of the revision battle. One reader
   independently rejected a snippet timestamped *after the question's own
   hour* — date-stamped memory enables temporal hygiene the haystack denies.
4. **Weakest cells are retrieval-shaped, not memory-shaped**:
   single-session-assistant (0.57) fails because answers live in long
   assistant turns truncated at 700 chars and user-phrased questions
   embed-match user turns; multi-session (0.69) because k=15 spreads thin
   when evidence spans many sessions. Both are reranker/chunking problems —
   the known engineering gap between us and the 90%+ vendor systems.

## Artifact

`ingest_demo.py` ingests one sampled question's full haystack (477 turn-gems,
44 sessions, 22 day-shards at `sessions/<date>/s<i>/<role>-t<j>`) into a real
Gemmery store — `browser.html` to see LongMemEval memory as a filesystem.
Fittingly, the sampled question is knowledge-update: "How many different
species of birds have I seen?" — a count that changes across sessions
(gold: 32).

Reproduce: `build_lme.py` (sample, embed, retrieve, oracle recall, reader
prompts) → 6 reader agents → `judge_and_score.py judge` → 2 judge agents →
`judge_and_score.py score`. Data: `data/lme/` (gitignored, ~290MB from
HuggingFace `xiaowu0162/longmemeval-cleaned`).

Sources: [Zep blog](https://blog.getzep.com/state-of-the-art-agent-memory/),
[Zep vs Mem0 comparison](https://atlan.com/know/zep-vs-mem0/),
[Emergence AI](https://www.emergence.ai/blog/sota-on-longmemeval-with-rag),
[Mastra observational memory](https://mastra.ai/research/observational-memory),
[ByteRover](https://www.byterover.dev/blog/benchmark_ai_agent_memory_real_production_byterover_top_market_accuracy_longmemeval).

---

## v2: the mechanical upgrades (`build_lme2.py`) — 0.733 → 0.917

Emergence's disclosed ablations predicted ~+9 pts from retrieval engineering
alone. We got +18.4, with **still zero LLM calls at ingestion**:

1. **Match on turns, retrieve whole sessions** — bi-encoder top-80 turns →
   local cross-encoder (`ms-marco-MiniLM-L-6-v2`) rerank → NDCG-style session
   scoring → top-4 sessions verbatim (Emergence's disclosed method).
2. **No more 700-char truncation** (v1's single-session-assistant killer).
3. **Snippet safety net**: top reranked turns from outside the chosen
   sessions (multi-session evidence spans >4 sessions).
4. **CoT reader**: quote memory lines + dates, do date arithmetic, then answer.

Same 60 questions, same judge protocol — the delta is attributable.

| ability type | v1 | v2 |
|---|---|---|
| multi-session | 0.69 | **1.00** |
| single-session-assistant | 0.57 | **1.00** |
| single-session-user | 0.88 | **1.00** |
| temporal-reasoning | 0.69 | **0.88** |
| knowledge-update | 0.89 | 0.89 |
| single-session-preference | 0.75 | 0.50 |
| abstention subset | 1.00 | **1.00** |
| **overall** | 0.733 | **0.917** |

Judge-free: oracle recall rose 0.923 → **0.962** (sessions + snippets).

Where 0.917 lands: above Emergence's disclosed 82.4/86%, at ByteRover's 92.8,
below Mastra's 94.87 — all of which are full-500 runs; ours is the n=60
sample with a local reranker and mechanical ingestion. Honest cost: whole
sessions are ~10K memory tokens/question vs v1's 1.8K (11× haystack
compression instead of 64×); reader spend ~4× v1.

**The 5 remaining misses, autopsied** (`judge2.py score`, verdicts in
`results_v2.json`):
- 2 genuine retrieval gaps — evidence diffused beyond the top-4 sessions
  (a 3-event temporal ordering; a preference question whose gold wants
  specific high-school memories).
- 1 reader oversight — abstained although the evidence was retrieved.
- 1 marginal judge call — suggested podcasts/audiobooks; gold wanted
  *new-genre* podcasts specifically.
- 1 benchmark artifact, both runs: the "3 months in Harajuku" gold evidence
  is timestamped **12 hours after the question's own timestamp**; the reader
  refused the future-stamped line and computed 7 months from an earlier
  anchor. Strict temporal hygiene loses to a gold label that ignores it.

**Reading of the ladder**: 0.733 (cosine + truncated turns) → 0.917
(rerank + whole sessions + CoT) → ~0.95 (Mastra: LLM-written observations,
no retrieval). The last rung is write-time intelligence — the librarian.
The remaining misses are consistent with that: what fails now is evidence
*aggregation* across sessions, which is exactly what distilled, dated,
revised observations solve.

---

## v3: the librarian arm (write-time intelligence) — a measured negative

Mirroring Mastra's architecture: question-blind Haiku observers distill each
user's full history into dated atomic observations at stable topic slugs;
slug reuse = `revise()` (real git version chains in `store_v3_1/`); the
reader gets the WHOLE distilled memory, no retrieval.

| arm | compression | overall |
|---|---|---|
| v1 cosine retrieval, truncated turns | 64× (reader-side) | 0.733 |
| **v2 rerank + whole sessions (raw record)** | 11× (reader-side) | **0.917** |
| v3.0 librarian, starved budget (1.4 obs/session) | 50× (write-side) | 0.367 |
| v3.1 librarian, comprehensive budget | 23× (write-side) | 0.500 |

Diagnosis (`results_v3.json`, `results_v4.json`):
- **v3.0's failures were 32/38 honest omissions** — the reader said "I don't
  know" because the observer never wrote the fact down. Only 6 confabulations.
  The system doesn't lie when memory is lossy; it abstains.
- v3.1 doubled capture (5,726 topics, 1,449 revision chains vs 3,374/331)
  and recovered single-session-user to 0.88 (headline facts survive), but
  temporal-reasoning (0.31) and multi-session (0.44) stay broken: the
  observer cannot know which INCIDENTAL detail (an exact time, which event
  came third) a future question will hinge on.
- **Abstention: 8/8 in all four runs** — the single most robust result of
  the benchmark. Bounded, dated memory gives calibrated absence-detection
  regardless of how the memory was built.
- Knowledge-update stayed high through every arm that had dated version
  chains — revision semantics survive even heavy compression.

**The law: the raw record beats a bad summary.** Write-time intelligence is
a bet that the observer can predict what will matter. On arbitrary needle
questions that bet fails at 23-50× compression — question-blind distillation
loses to keeping everything and retrieving carefully. This is the simulate
experiment's fidelity law surfacing at write time: lossy memory faithfully
read is worth little, exactly as a miscalibrated model faithfully simulated
was worth nothing. Mastra's 94.87% is not "LLM at write beats retrieval" —
it is LLM at write **at 3-6× compression** (4-8× fatter than our v3.1),
with a reflector pass. Whether our arm closes the gap at that budget is
untested (extrapolation from 50×→23× = +13.3 pts suggests much but not all).

**Why this vindicates the architecture rather than indicting it:** Gemmery's
store keeps the full record immutable and treats distillation (dossiers) as
an ADDITION that cites it, never a replacement. The v2 arm — the one at
0.917 — runs on exactly that principle. The SWE librarian worked (top-1
1.000) because it distilled *method rules*, which transfer as gist; needle
facts don't. Distill judgment, retrieve facts.

Cost: 60 Haiku observers/run × ~115K-token read (the write-time pass reads
the corpus once — same input volume as one full-context sweep, amortized
across every future question), readers ~2× cheaper than v2 (distilled
memory is smaller than 4 raw sessions).
