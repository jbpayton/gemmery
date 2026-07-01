"""Scaled Gnosia memory experiment: does selective retrieval beat dump-everything?

Train/test split: 60 training games build the memory (24-persona pool); 12
held-out test games are judged by an LLM observer that must name a Gnosia. Three
arms, all making the same 12 decisions:

  * gemmery — retrieve ONLY the 8 present players' records (selective)
  * md      — read the WHOLE notes.md (all 24 personas, all 60 games)
  * cold    — transcript only

The memory is deliberately large and heterogeneous: for any test game only 8 of
24 personas are relevant, so the .md dump is mostly noise the reader must sift,
while Gemmery hands over the relevant slice. This is the regime where structure
should finally earn its keep over a flat file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from engine import make_pool, run_game, behavior_summary  # noqa: E402

from gemmery import (Action, Cost, Gem, GitStore, IndexKeys, Kind,  # noqa: E402
                     KnowledgeBody, Provenance, TestSpec)
from gemmery.index import GemIndex  # noqa: E402
from gemmery.baselines import MarkdownMemory  # noqa: E402

POOL_SIZE, N_PLAYERS, N_GNOSIA = 24, 8, 2
TRAIN, TEST = 60, 8
TEST_SEEDS = list(range(9000, 9000 + TEST))


def record_text(g, i, pid) -> str:
    role = "GNOSIA" if pid in g.gnosia_set() else g.roles[pid].value
    return f"Game {i}: {pid}'s true role was {role}. That game {pid} {behavior_summary(g, pid)}."


def _gem(pid, i, g):
    role = "GNOSIA" if pid in g.gnosia_set() else g.roles[pid].value
    return Gem(kind=Kind.knowledge,
               provenance=Provenance(actor="gnosia-log", session_id="hist", timestamp=float(i)),
               body=KnowledgeBody(action=Action("record", {"player": pid}),
                                  reasoning=record_text(g, i, pid),
                                  belief=f"{pid} tendencies",
                                  tests=[TestSpec(f"role::{pid}", "reveal", "ok")]),
               cost=Cost(),
               index_keys=IndexKeys(precondition_shape=[role.lower()],
                                    action_type="past_game", domain=[pid],
                                    test_ids=[f"role::{pid}"]))


HEADER = (
    "You are an expert observer of a Gnosia-style social-deduction game. Players "
    "have hidden roles: Crew, Engineer (night scan), Doctor (autopsy), Guardian "
    "Angel, Guard, AC Follower (a HUMAN who secretly sides with the Gnosia), and "
    "2 hidden GNOSIA. A power-role claim may be truthful or a Gnosia's lie.\n"
    "For EACH game below, name the ONE player you most suspect is a GNOSIA "
    "(not merely suspicious — actually a Gnosia).\n"
    "{mem_help}"
    "Return ONLY a JSON object mapping each game id to your pick, e.g. "
    '{{"T0": "P07", "T1": "P12"}}.\n\n')
MEM_HELP = ("You have RECORDS of past games with these same players. A player's "
            "behavior when they were a Gnosia versus when they were human is the "
            "key — especially which power role each tends to FAKE-claim when "
            "they are a Gnosia (that resolves who is lying in a counter-claim).\n")


def build():
    pool = make_pool(POOL_SIZE)
    train = [run_game(s, pool, N_PLAYERS, N_GNOSIA) for s in range(TRAIN)]
    test = [run_game(s, pool, N_PLAYERS, N_GNOSIA) for s in TEST_SEEDS]

    # Gemmery store + index (for selective retrieval), and one flat markdown file.
    store = GitStore(ROOT / "store")
    md = MarkdownMemory(ROOT / "notes.md"); md.clear()
    for i, g in enumerate(train):
        for pid in g.players:
            store.capture(_gem(pid, i, g))
            md.capture(record_text(g, i, pid))
    index = GemIndex(db_path=str(ROOT / "idx.sqlite")); index.rebuild(store)

    truth = {f"T{j}": list(g.gnosia_set()) for j, g in enumerate(test)}
    json.dump(truth, open(ROOT / "truth.json", "w"), indent=1)

    full_dump = md.read_all()

    def selective(g) -> str:
        blocks = []
        for pid in g.players:
            shas = index.columnar_filter(domain=pid)
            recs = sorted(store.read_gem(s).reasoning_text() for s in shas)
            if recs:
                blocks.append(f"Records for {pid}:\n" + "\n".join("  - " + r for r in recs))
        return "\n".join(blocks)

    # PER-GAME prompts (one decision per call) so Gemmery's focused slice
    # competes with md's full dump for the *same* decision — a fair per-decision
    # comparison, not an artifact of batching.
    (ROOT / "prompts").mkdir(exist_ok=True)

    def game_block(g, j):
        return f"===== GAME T{j} (players: {', '.join(g.players)}) =====\n{g.public_transcript()}\n"

    for j, g in enumerate(test):
        # gemmery: transcript + selective retrieval of this game's 8 players
        gem = (HEADER.format(mem_help=MEM_HELP) + game_block(g, j)
               + "\n[Retrieved records for THIS game's players]\n" + selective(g) + "\n")
        (ROOT / "prompts" / f"gemmery_T{j}.txt").write_text(gem)
        # md: transcript + the WHOLE notes.md (all 24 personas)
        mdp = (HEADER.format(mem_help=MEM_HELP)
               + f"[Your notes.md — every past game you've recorded]\n{full_dump}\n\n"
               + game_block(g, j))
        (ROOT / "prompts" / f"md_T{j}.txt").write_text(mdp)

    # cold: one batched call (no memory to repeat)
    cold = HEADER.format(mem_help="")
    for j, g in enumerate(test):
        cold += game_block(g, j) + "\n"
    (ROOT / "prompts" / "cold.txt").write_text(cold)

    sizes = {
        "gemmery_per_game": (ROOT / "prompts" / "gemmery_T0.txt").stat().st_size,
        "md_per_game": (ROOT / "prompts" / "md_T0.txt").stat().st_size,
        "cold_batched": (ROOT / "prompts" / "cold.txt").stat().st_size,
    }
    return truth, sizes, len(md.read_all())


if __name__ == "__main__":
    truth, sizes, dump_chars = build()
    print(f"pool={POOL_SIZE} players/game={N_PLAYERS} gnosia={N_GNOSIA} "
          f"train={TRAIN} test={TEST}")
    print("full notes.md dump chars:", dump_chars)
    print("prompt sizes (bytes):", {k: v for k, v in sizes.items()})
    print("gnosia per test game (chance = 2/8 = 0.25):",
          {g: len(v) for g, v in truth.items()})
