# Adversarial memory — Werewolf results

**Why this experiment.** The task-solving pilots hit a wall: a strong model
solves textbook tasks cold, so memory has no headroom. An *adversarial* game
dissolves that — the metric is *relative* (edge vs equally-capable play), and the
memory content (an opponent's behavioral tells) is **unknowable cold**, so the
model can't fall back on its own knowledge. This directly tests: does memory of
past encounters confer a competitive edge?

**Game.** 5 players; P0 is the focal Villager (role fixed to hold variance out);
P1-P4 are scripted personas, exactly one the Werewolf each game. Each persona has
a distinct **villager baseline** and a distinct **wolf tell** (e.g. P2 is silent
as a villager but fakes a Seer claim as the wolf; P1 accuses a fixed rival as a
villager but accuses the focal seat as the wolf). You cannot tell a tell from
normal behavior without the player's baseline — and the baseline lives only in
memory of past games. Past games are captured as gems in a real Gemmery
`GitStore`; the memory arm retrieves the current players' prior records via the
index.

## Result 1 — the mechanic (deterministic, no LLM, 200 games)

| reader | wolf-ID accuracy |
|---|---|
| memoryless heuristic | **0.07** |
| memory (profiles from prior games) | **0.98** |
| chance | 0.25 |

The memoryless reader is *below chance* — the fake-Seer tell actively **traps**
it (it trusts the wolf's Seer claim). Memory accuracy climbs 0.70 → 1.00 over the
first ~30 games as baselines accumulate. So the tells are genuinely learnable
only from history.

## Result 2 — LLM focal (real sub-agents, matched compute)

Two Claude sub-agents judged the same 11 games (memory grows across them), each
making one decision per game. The memory arm got retrieved past-game records; the
cold arm got the transcript only (the browse+empty-memory control).

| LLM focal (11 games) | wolf-ID accuracy |
|---|---|
| **+ memory** (Gemmery, retrieved history) | **11/11 = 1.00** |
| **+ .md** (plain markdown, read-it-all) | **11/11 = 1.00** |
| **+ cold** (empty memory) | **4/11 = 0.36** |
| **Δ (memory effect over cold)** | **+0.64** |

The cold agent hovered just above chance and fell into the same trap (a heavy
P1/P2 bias from false tells). Both memory arms inferred each player's
baseline-vs-wolf signature from *raw records we did not label for them* and
identified the wolf every time — the Gemmery arm on slightly **fewer** tokens
than the cold arm (34.2k vs 35.8k), so the win is memory content, not compute.

### Result 3 — does the memory *substrate* matter? (the `.md` baseline)

We added a third arm: a plain **markdown** scratchpad (`gemmery.baselines.
MarkdownMemory`) — append notes, read the whole file back, no index, no selective
retrieval. **It ties Gemmery at 1.00.** The honest reading, and exactly the
distinction the baseline was built to expose:

- **Memory *content* is load-bearing** (+0.64 over cold) — established.
- **Gemmery's *structure* is NOT load-bearing here** — a flat scratchpad does
  just as well. At this scale (small history, fixed 4-player pool, every record
  relevant) there is nothing to select or scale, so "dump everything" is fine.
- The only measured difference is **efficiency**: the Gemmery prompt was 28 KB
  vs the markdown arm's 74 KB (it re-dumps the whole growing file each turn).
  Gemmery's structural advantages — selective retrieval, bounded context,
  browsing a large/heterogeneous store, credit — should only *pay in accuracy*
  once the memory is big and diverse enough that reading it all breaks down
  (context limits, distraction, cost). Demonstrating that is the next test:
  scale the opponent pool and history so selectivity matters.

This is the kill-switch applied to Gemmery itself: it cleanly separates "memory
helps" (yes) from "Gemmery's machinery beats a text file" (not yet, not at this
scale) — and says precisely what regime would change the answer.

## Honest scope

- This is the **experiential / opponent-modeling** regime — the "easier" claim
  (memory is *known* to help when it carries information the model lacks). It is a
  clean, compelling demonstration of the mechanism, **not** a resolution of the
  hard cross-problem method-transfer question.
- Opponents are **scripted with consistent tells** (semi-synthetic); that is what
  makes memory decisive and the effect measurable at small n. A full all-LLM
  tournament (opponents also reasoning, noisier tells) is the richer follow-on
  and would show a smaller effect.
- n = 11 LLM games, single run — exploratory; the 200-game deterministic
  validation is the statistical backbone.
- **Open question this raises (the next test):** does Gemmery's *structure*
  (selective retrieval, immutable records, browsing) actually beat a plain
  markdown notes file here? At this scale — small memory, fixed player pool, all
  records relevant — a flat "dump everything" note may do just as well. See the
  `.md` baseline comparison.

Reproduce: `python experiments/werewolf/engine.py`-driven validation is in
`build_experiment.py`; scoring in `score.py` (committed agent answers reproduce
the numbers).
