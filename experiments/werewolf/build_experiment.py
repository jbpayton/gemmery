"""Build the LLM-focal Werewolf memory experiment, routed through real Gemmery.

Past games are captured as gems in a GitStore (one per scripted player per game,
tagged by player). For each focal-judged game we retrieve that game's players'
prior history from the index and assemble the memory block. Two arms, matched on
model-calls (one focal decision per game):

  * memory  — transcript + retrieved past-game records for P1-P4
  * cold    — transcript only (browse+empty-memory control)

The focal's job: name the werewolf. The memory arm must *infer the tells* from
raw past records (we do not hand it the answer) — honest memory use.
"""

from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import SCRIPTED, run_game, Game  # noqa: E402

from gemmery import (Action, Cost, GitStore, IndexKeys, Kind, KnowledgeBody,  # noqa: E402
                     Provenance, TestSpec)
from gemmery.index import GemIndex  # noqa: E402

ROOT = Path(__file__).resolve().parent
POOL = 45                       # games that form the accumulated history
FOCAL_GAMES = [3, 5, 8, 12, 20, 24, 28, 32, 36, 40, 44]  # judged at growing memory


def player_behavior(game: Game, pid: str) -> str:
    ss = [s for s in game.statements if s.speaker == pid]
    bits = []
    if any(s.claims_seer for s in ss):
        bits.append("claimed to be the Seer")
    accuses = [s.accuses for s in ss if s.accuses and not s.claims_seer]
    if any(s.round == 1 and s.silent for s in ss):
        bits.append("stayed silent on Day 1")
    if accuses:
        bits.append("accused " + ", then ".join(accuses))
    return "; ".join(bits) or "did nothing notable"


def capture_history(store: GitStore, games: list[Game]) -> None:
    for i, g in enumerate(games):
        for pid in SCRIPTED:
            role = "WEREWOLF" if pid == g.wolf else "villager"
            gem = _obs_gem(pid, i, role, player_behavior(g, pid))
            store.capture(gem)


def _obs_gem(pid, game_idx, role, behavior):
    return __import__("gemmery").Gem(
        kind=Kind.knowledge,
        provenance=Provenance(actor="werewolf-log", session_id="history",
                              timestamp=float(game_idx)),
        body=KnowledgeBody(
            action=Action("record_behavior", {"player": pid}),
            reasoning=f"Game {game_idx}: {pid} was the {role}. That game {pid} {behavior}.",
            belief=f"{pid} behaves a certain way as {role}",
            tests=[TestSpec(f"role::{pid}", "later reveal", "role confirmed")],
        ),
        cost=Cost(),
        index_keys=IndexKeys(precondition_shape=[role.lower(), f"g{game_idx}"],
                             action_type="past_game", domain=[pid],
                             test_ids=[f"role::{pid}"]),
    )


def memory_block(store: GitStore, index: GemIndex, k: int, per_player: int = 8) -> str:
    """Retrieve each current player's prior-game records (games < k) via the index."""
    lines = []
    for pid in SCRIPTED:
        shas = index.columnar_filter(domain=pid)
        recs = []
        for sha in shas:
            gem = store.read_gem(sha)
            if gem.provenance.timestamp < k:  # leave-one-out: strictly past games
                recs.append((gem.provenance.timestamp, gem.reasoning_text()))
        recs.sort()
        if recs:
            lines.append(f"Past games with {pid}:")
            for _, txt in recs[-per_player:]:
                lines.append(f"  - {txt}")
    return "\n".join(lines) or "(no prior history)"


HEADER = (
    "You are P0, a Villager in a game of Werewolf with players P1, P2, P3, P4. "
    "Exactly ONE of them is the Werewolf. Below are one or more independent "
    "games: for each, read the day-phase statements and decide who is most "
    "likely the Werewolf.\n"
    "{mem_help}"
    "A Seer claim may be genuine or a werewolf's lie — judge from behavior.\n"
    "Return ONLY a JSON object mapping each GAME id to your pick, e.g. "
    "{{\"G3\": \"P2\", \"G5\": \"P1\"}}. Picks must be one of P1..P4.\n\n"
)
MEM_HELP = ("You ALSO have notes from PAST games with these same players. A "
            "player's normal (villager) behavior versus how they act when they "
            "were the werewolf is the key to reading this game's tells.\n")


def md_notes_block(games, k: int) -> str:
    """The naive `.md` baseline: append every prior game's records to a markdown
    file and read the WHOLE thing back (no structure, no selective retrieval).
    Same information as the Gemmery arm — only the organization differs."""
    from gemmery.baselines import MarkdownMemory
    mem = MarkdownMemory(ROOT / f"notes_G{k}.md")
    mem.clear()
    for i in range(k):
        g = games[i]
        for pid in SCRIPTED:
            role = "WEREWOLF" if pid == g.wolf else "villager"
            mem.capture(f"Game {i}: {pid} was the {role}. That game {pid} "
                        f"{player_behavior(g, pid)}.")
    return mem.read_all()


def build(arm: str) -> dict:
    games = [run_game(s) for s in range(POOL)]
    store = index = None
    if arm in ("memory",):
        store = GitStore(ROOT / f"store_{arm}")
        capture_history(store, games)
        index = GemIndex(db_path=str(ROOT / f"idx_{arm}.sqlite"))
        index.rebuild(store)

    body = HEADER.format(mem_help=(MEM_HELP if arm in ("memory", "md") else ""))
    truth = {}
    for k in FOCAL_GAMES:
        g = games[k]
        truth[f"G{k}"] = g.wolf
        body += f"===== GAME G{k} =====\n{g.transcript()}\n"
        if arm == "memory":  # Gemmery: structured, per-player retrieval
            body += "\n[Memory — prior games with these players]\n"
            body += memory_block(store, index, k) + "\n"
        elif arm == "md":    # naive baseline: read the whole notes.md
            body += "\n[Your notes.md — everything you've written so far]\n"
            body += md_notes_block(games, k) + "\n"
        body += "\n"
    (ROOT / f"prompt_{arm}.txt").write_text(body)
    return truth


if __name__ == "__main__":
    t1 = build("memory")
    t2 = build("cold")
    t3 = build("md")
    assert t1 == t2 == t3
    json.dump(t1, open(ROOT / "truth.json", "w"), indent=1)
    print(f"built {len(t1)} focal games x 3 arms (pool={POOL})")
    print("focal games (memory grows across them):", FOCAL_GAMES)
    print("wrote prompt_memory.txt, prompt_cold.txt, truth.json")
    # show a snippet of the memory block for the last focal game
    print("\n--- sample memory block (game G44, player excerpt) ---")
    games = [run_game(s) for s in range(POOL)]
    store = GitStore(ROOT / "store_memory")
    index = GemIndex(db_path=str(ROOT / "idx_memory.sqlite")); index.load_vectors()
    print("\n".join(memory_block(store, index, 44).splitlines()[:9]))
