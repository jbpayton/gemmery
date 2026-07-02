# Drift evaluation — append-only notes vs revised dossiers

**Question.** The upgraded store's new capability is *revision at a stable path*
(dossiers that stay current while history is retained). Does that beat the
classic append-only `notes.md` when a player's behavior **inverts** mid-history?

**Setup.** 60 games; at game 45, P2's tells invert (Seer-claim goes from wolf
tell → innocent habit; silence goes from innocent baseline → wolf tell). Others
stable. Current-regime wolves *hide* their tell half the time. Arms, one focal
LLM each, same 8 test games: `cold` (transcripts only); `md` (chronological
notes.md, 17.7 KB, contradictions included); `gemmery` (mechanically-templated
dossiers **revised** post-drift from a recency window, 2.9 KB; superseded
versions in `history(path)`, revision `consumed` the post-drift observations —
built on the real store).

## Result

| arm | overall | wolf showed tell | stale trap (wolf hid) | P2-wolf (new silent tell) |
|---|---|---|---|---|
| cold | 0.25 | 0/2 | 0/3 | 2/2* |
| md (append) | **0.50** | 2/2 | 1/3 | 0/2 |
| gemmery (revised) | **0.50** | 2/2 | 1/3 | 0/2 |

\* cold guessed P2 every game — accidentally right exactly in the P2-wolf cell.

- **Memory content helps (+0.25 over cold), and the substrates TIE again.** The
  md agent handled the contradictory chronology fine — it inferred recency on
  its own. At 60 games (fits comfortably in context), a raw log and a curated
  current-view are equally *readable*; revision is a **write-time compression**
  (6× smaller prompt) and a **provenance** win, not an accuracy edge.
- **Both memory arms read shown tells perfectly** (2/2) and were capped near the
  1/3 information-theoretic ceiling when the wolf hid perfectly.
- **The interesting failure:** in the P2-wolf cell, the gemmery dossier said
  explicitly *"current wolf-indicative behavior: silent"* — P2 was silent — and
  the agent still picked someone else (both memory arms 0/2, with visible pick
  biases: md leaned P3, gemmery leaned P1). The knowledge was retrieved but not
  **applied** — the model's social-deduction priors overrode the dossier. This
  is the same application-bottleneck seen in `complex_rules` (retrieve-then-
  reason underperformed retrieve-then-aggregate). The memory system delivered;
  the reasoning layer dropped it.

## Where this leaves the substrate scorecard

Consistent with every prior round: **while the relevant memory fits in context,
substrate does not move accuracy** — not for recall (werewolf), not at 24
personas (gnosia), not under drift (here). The structured store's measured wins
remain: exact aggregation at scale, staying current when history *overflows*
context (integrated experiment: stale markdown planned below no-memory), token
efficiency (6× here), and the audit/provenance/post-hoc-explanation axis. And a
recurring lesson for the *skill* layer: the binding failure is increasingly the
model **applying** what memory hands it — worth encoding as "trust the dossier's
explicit conclusion over your priors" guidance in SKILL.md.

Reproduce: `python experiments/drift/build.py`, run the three arms, then
`python experiments/drift/score.py`; graph via `plot.py`.
