# LongMemEval: Gemmery's first externally-comparable number

**0.733 overall (44/60)** on a stratified sample of LongMemEval_S (cleaned),
with **perfect abstention (8/8)** and **0.89 on knowledge-update** — the two
categories that map onto Gemmery's calibration and revision machinery.

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
