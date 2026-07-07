# P1: Gemmery develops Gemmery (the dogfood loop)

Production phase 1, live in this repo via `.claude/settings.json` hooks:

| hook | script | job |
|---|---|---|
| SessionStart | `inject.py` | inject earned dossiers (versions, W/L, credit lead) + cite-as-[[path]] instruction |
| PostToolUse (Bash) | `outcome_hook.py` | append pytest pass/fail to `.gemmery-store/outcomes.jsonl` (no LLM) |
| SessionEnd | `librarian.py` | 1) fold outcomes -> `tag_outcome` + success/credit notes on dossiers with matching declared tests (fail debits 2x); 2) one `claude -p` (haiku, `GEMMERY_LIBRARIAN_MODEL` to override) distills the transcript tail into capture/revise ops |

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

Manual runs: `.venv/bin/python tools/prod/inject.py` (see what sessions see);
`echo '{}' | .venv/bin/python tools/prod/librarian.py <transcript.jsonl>`.
Store: `.gemmery-store/` (gitignored; it's git — back up with a remote).
