# Scaled adversarial memory — Gnosia results

**Goal.** Scale the Werewolf demo to full Gnosia-style rules (Crew, Engineer,
Doctor, Guardian Angel, Guard, AC Follower, + variable Gnosia) drawn from a
large **24-persona pool** (8 per game), so that for any one game only a *slice*
of the memory is relevant. This is the regime where selective retrieval
(Gemmery) should finally beat "read the whole notes file" (`.md`) — the test the
previous round set up.

**Setup.** 60 training games build the memory; 8 held-out games are judged by an
LLM observer that must name a Gnosia (chance 2/8 = 0.25). Three arms, one
decision per call each: **gemmery** (retrieve only this game's 8 players'
records, ~15 KB), **md** (read the whole notes.md — all 24 personas, ~42 KB),
**cold** (transcript only). Each persona has a fixed tell — chiefly *which power
role it fake-claims when it is a Gnosia* — so counter-claims ("two Guardian
Angels") are only resolvable from that persona's history.

## Deterministic backbone (400 games)

Per-persona memory detector **0.81** vs memoryless **0.34** (chance 0.25); curve
climbs 0.60 → 0.85. The tells are strongly learnable.

## LLM result

| arm | Gnosia-ID accuracy |
|---|---|
| cold (no memory) | 6/8 = **0.75** |
| plain `.md` (dump all 24) | 7/8 = **0.88** |
| Gemmery (retrieve 8) | 7/8 = **0.88** |
| memory effect (best − cold) | **+0.13** |
| **selective-retrieval effect (Gemmery − md)** | **+0.00** |

The memory arms reason exactly as intended — e.g. *"P14 never claims a power role
when it's a Gnosia, so its Engineer scan here is credible → the flagged player is
Gnosia"*, and resolving a Guardian-Angel counter-claim via *"P00 has only ever
claimed GA as a Gnosia (5/5) and was never the real GA in 15 games."*

## Two honest findings

1. **Memory helps only modestly here (+0.13), far less than Werewolf (+0.64).**
   The LLM is *already strong at within-game deduction*: cold scores 0.75 (vs the
   naive deterministic cold's 0.34) because the transcript itself — scans,
   counter-claims — carries a lot of signal a good reasoner exploits without any
   history. The game leaks too much in-transcript information to leave much room
   for memory. (And memory can mislead: on T3 both memory arms confidently picked
   P00 from its GA-fake tell, but P00 wasn't Gnosia that game — the tell didn't
   hold, and all three arms missed.)

2. **Gemmery ties the markdown baseline again — +0.00.** Even at 24 personas and
   a ~42 KB dump, selective retrieval gives *no accuracy edge*: the LLM finds and
   applies the relevant players' tells fine from the full notes file. The only
   measured difference is **efficiency** — on the hardest game the md arm spent
   ~55 K tokens vs Gemmery's ~34 K for the same answer.

## The robust conclusion (across Werewolf + Gnosia)

Two independent experiments now agree: **memory *content* is load-bearing, but
Gemmery's *structure* is not — for accuracy, at these scales.** A flat markdown
scratchpad matches the git-DAG whenever the whole history still fits comfortably
in context. Gemmery's structural advantages (selective retrieval, bounded
context, browsing, credit) remain *efficiency* wins here, and would only convert
to *accuracy* wins once the memory is large enough to break "read it all" —
i.e. **hundreds of personas / MB-scale history that overflows the context
window or triggers real lost-in-the-middle degradation.** That, plus harder
games with less in-transcript signal, is what the next scale-up needs. This is
the kill-switch applied to Gemmery itself, twice: it keeps honestly reporting
that the fancy substrate hasn't yet earned its keep over a text file.

Reproduce: `python experiments/gnosia/build_experiment.py` then
`python experiments/gnosia/score.py`; graphs via `plot.py`.
