"""A small, measurable Werewolf variant for the adversarial-memory experiment.

5 players: P0 is the focal agent (always a plain Villager, to hold role-variance
out of the measurement); P1-P4 are scripted personas, exactly one of whom is the
Werewolf each game. Over two day-rounds the scripted players make public
statements (accusations / claims) governed by their persona AND their role. Then
the focal must name the wolf.

The design commitment that makes memory *decisive*: each persona has a distinct
**villager baseline** and a distinct **wolf tell**. You cannot tell a tell from
normal behavior without knowing the player's baseline — and the baseline only
exists in memory of past games. A memoryless reader is even *trapped* (e.g. a
wolf's fake "I'm the Seer" claim reads as helpful). This module is pure,
deterministic given a seed, and involves no LLM — it generates the games and
provides two reference detectors to validate that the tells are learnable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

PLAYERS = ["P0", "P1", "P2", "P3", "P4"]
SCRIPTED = ["P1", "P2", "P3", "P4"]
FOCAL = "P0"


@dataclass
class Statement:
    speaker: str
    round: int
    accuses: str | None = None
    claims_seer: bool = False
    silent: bool = False

    def render(self) -> str:
        if self.claims_seer:
            tgt = self.accuses or "someone"
            return f"{self.speaker}: \"I'm the Seer — I checked {tgt}, they're clean. Trust me.\""
        if self.silent:
            return f"{self.speaker}: (stays quiet, makes no accusation)"
        return f"{self.speaker}: \"I think {self.accuses} is the werewolf.\""


@dataclass
class Game:
    seed: int
    wolf: str
    statements: list[Statement] = field(default_factory=list)

    def transcript(self) -> str:
        lines = []
        for r in (1, 2):
            lines.append(f"--- Day {r} ---")
            for s in self.statements:
                if s.round == r:
                    lines.append("  " + s.render())
        return "\n".join(lines)

    def most_accused(self, upto_round: int) -> str | None:
        counts: dict[str, int] = {}
        for s in self.statements:
            if s.round <= upto_round and s.accuses and not s.claims_seer:
                counts[s.accuses] = counts.get(s.accuses, 0) + 1
        return max(counts, key=counts.get) if counts else None


# --------------------------------------------------------------------------- #
# Persona behaviour: role-conditioned, each with a distinct baseline + tell.
# --------------------------------------------------------------------------- #
def _persona_statement(pid: str, is_wolf: bool, rnd: int, game: Game,
                       rng: random.Random) -> Statement:
    if pid == "P1":
        # baseline villager: fixed grudge, accuses P2 both rounds.
        # WOLF TELL: accuses the focal villager P0 (wolves fear the sharp seat).
        return Statement(pid, rnd, accuses=("P0" if is_wolf else "P2"))

    if pid == "P2":
        # baseline villager: silent. WOLF TELL: fake Seer claim (there is no Seer).
        if is_wolf:
            clean = rng.choice([p for p in SCRIPTED if p != "P2"])
            return Statement(pid, rnd, claims_seer=True, accuses=clean)
        return Statement(pid, rnd, silent=True)

    if pid == "P3":
        # baseline villager: follows consensus (accuses current most-accused).
        # WOLF TELL: silent on Day 1, then counter-accuses its accuser on Day 2.
        if is_wolf:
            if rnd == 1:
                return Statement(pid, rnd, silent=True)
            accuser = next((s.speaker for s in game.statements
                            if s.round == 1 and s.accuses == "P3"), "P0")
            return Statement(pid, rnd, accuses=accuser)
        target = game.most_accused(rnd - 1) or rng.choice(
            [p for p in PLAYERS if p != "P3"])
        return Statement(pid, rnd, accuses=target)

    # P4: baseline villager fixed on P1. WOLF TELL: bandwagons the most-accused.
    if is_wolf:
        if rnd == 1:
            return Statement(pid, rnd, silent=True)
        return Statement(pid, rnd, accuses=(game.most_accused(1) or "P1"))
    return Statement(pid, rnd, accuses="P1")


def run_game(seed: int) -> Game:
    rng = random.Random(seed)
    wolf = rng.choice(SCRIPTED)
    game = Game(seed=seed, wolf=wolf)
    for rnd in (1, 2):
        for pid in SCRIPTED:
            game.statements.append(
                _persona_statement(pid, pid == wolf, rnd, game, rng))
    return game


# --------------------------------------------------------------------------- #
# Reference detectors (no LLM) — validate that the tells are learnable.
# --------------------------------------------------------------------------- #
def cold_detector(game: Game, rng: random.Random) -> str:
    """Memoryless heuristic: trust a Seer claim, else accuse the most-accused.

    This encodes the naive read — and the fake-Seer tell deliberately *traps* it.
    """
    for s in game.statements:
        if s.claims_seer:  # believes the (fake) seer -> suspects whoever seer 'cleared' the least
            others = [p for p in SCRIPTED if p != s.speaker]
            return rng.choice(others)  # misled: never suspects the claimer
    return game.most_accused(2) or rng.choice(SCRIPTED)


def build_profiles(past: list[Game]) -> dict[str, dict]:
    """Per-persona memory: how often each behaviour co-occurs with being wolf."""
    prof: dict[str, dict] = {p: {"wolf_games": 0, "villager_games": 0,
                                 "seer_claim_as_wolf": 0, "seer_claim_as_vil": 0,
                                 "accuse_P0_as_wolf": 0, "accuse_P0_as_vil": 0,
                                 "silent_d1_as_wolf": 0, "silent_d1_as_vil": 0}
                             for p in SCRIPTED}
    for g in past:
        for pid in SCRIPTED:
            w = (pid == g.wolf)
            prof[pid]["wolf_games" if w else "villager_games"] += 1
            ss = [s for s in g.statements if s.speaker == pid]
            if any(s.claims_seer for s in ss):
                prof[pid]["seer_claim_as_wolf" if w else "seer_claim_as_vil"] += 1
            if any(s.accuses == "P0" and not s.claims_seer for s in ss):
                prof[pid]["accuse_P0_as_wolf" if w else "accuse_P0_as_vil"] += 1
            if any(s.round == 1 and s.silent for s in ss):
                prof[pid]["silent_d1_as_wolf" if w else "silent_d1_as_vil"] += 1
    return prof


def memory_detector(game: Game, profiles: dict[str, dict],
                    rng: random.Random) -> str:
    """Score each suspect by how much this game's behaviour matches their known
    *wolf* signature vs their *villager* baseline (a simple likelihood ratio)."""
    def rate(pid, key_w, key_v):
        p = profiles[pid]
        wg, vg = max(p["wolf_games"], 1), max(p["villager_games"], 1)
        return (p[key_w] / wg) - (p[key_v] / vg)

    best, best_score = None, -1e9
    for pid in SCRIPTED:
        ss = [s for s in game.statements if s.speaker == pid]
        score = 0.0
        if any(s.claims_seer for s in ss):
            score += rate(pid, "seer_claim_as_wolf", "seer_claim_as_vil")
        if any(s.accuses == "P0" and not s.claims_seer for s in ss):
            score += rate(pid, "accuse_P0_as_wolf", "accuse_P0_as_vil")
        if any(s.round == 1 and s.silent for s in ss):
            score += rate(pid, "silent_d1_as_wolf", "silent_d1_as_vil")
        score += rng.random() * 1e-6  # deterministic tie-break
        if score > best_score:
            best, best_score = pid, score
    return best or rng.choice(SCRIPTED)
