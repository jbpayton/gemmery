# P1: Gemmery develops Gemmery (the dogfood loop)

Production phase 1, live in this repo via `.claude/settings.json` hooks:

As of P3 the loop ships WITH the package (`gemmery/prod/`): any project gets
it via `pip install gemmery && gemmery init` (creates `.gemmery-store/`, wires
the hooks, idempotent, merge-safe). This repo's hooks call the same packaged
commands:

| hook | command | job |
|---|---|---|
| SessionStart | `gemmery inject` | inject earned dossiers (versions, W/L, credit lead) + cite-as-[[path]] instruction |
| PostToolUse (Bash) | `gemmery outcome-hook` | append pytest pass/fail to `.gemmery-store/outcomes.jsonl` (no LLM, redacted) |
| SessionEnd | `gemmery librarian` | 1) fold outcomes -> `tag_outcome` + success/credit notes on dossiers with matching declared tests (fail debits 2x); 2) one `claude -p` (haiku, `GEMMERY_LIBRARIAN_MODEL` to override) distills the transcript tail into capture/revise ops; 3) `git gc --auto` |

Design carries the measured laws: **distill judgment, retrieve facts** (dossiers
hold rules/rationale/citations into code+commits, never restatements — the repo
IS the raw record); revise-not-fork at stable `knowledge/` paths; selectivity
(0-2 items/session, empty is good); numbers lead in the injection; failures
debit harder than successes credit.

## The P1 gate (evaluate after ~2 weeks of real sessions)

Open-loop credit is the one thing no experiment tested — outcomes here arrive
late, messy, or never. The gate:

1. **Use**: do transcripts contain `[[knowledge/...]]` citations of injected
   dossiers? (grep the transcript dir)
2. **Revision**: do dossiers acquire versions (`history()` > 1) from
   falsifying sessions, or only accumulate?
3. **Credit flow**: do outcome tags actually land (librarian.log
   `outcomes tagged=N` > 0 across sessions)?
4. **Selectivity holds**: ops/session stays ~0-2 (librarian.log), no junk
   drawer.

Pass -> P2 hardening (multi-writer locks via branch-per-session + adjudication,
index-as-read-path for history, 100K-gem torture, secrets filtering).
Fail -> the failure mode itself is the next experiment.

Manual runs: `gemmery inject` (see what sessions see);
`echo '{}' | gemmery librarian <transcript.jsonl>`.
Store: `.gemmery-store/` (gitignored; it's git — back up with a remote).

## P2 hardening (complete) — measured at 100K gems

| property | result |
|---|---|
| capture latency | **flat 3.0→3.25ms median** across 100K (p99 <=12ms); <25ms invariant holds 8x over |
| concurrent writers | 4 processes, zero lost commits / zero lost note events (flock on all mutators) |
| secrets | redacted at the capture boundary (AWS/GitHub/Anthropic/OpenAI/Slack/JWT/PEM/bearer), plus the outcome ledger |
| history() at 100K | git-log 3,478ms -> **pathlog 137ms (25x)**, exact parity, 1s one-time migration |
| repo size | 4.2GB loose -> **87MB after gc (48x)**; librarian runs `gc --auto` at session end |
| point reads | read_gem 0.2ms, ls 0.1ms |

The pathlog sidecar is derived data (git stays the source of truth;
`rebuild_pathlog()` regenerates it). Non-main branches keep git-log history
semantics (a frontier's history legitimately includes its branch point's).
Numbers: `tools/scale_results.json`, harness `tools/scale_torture.py`,
tests `tests/test_hardening.py`.
