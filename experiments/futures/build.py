"""Branch the future: fork one git branch per candidate decision, simulate each
forward, inhabit them, diff them, choose — then explain the roads not taken.

Continues the played game (wolf = P2, fake-Seer trap) using the focal's ACTUAL
captured Round-1 belief. The game now has a consequential move: P0's Day-1 vote
is decisive. Rules for the simulated future:

  * Day 1: the village follows P0's vote. Voting the wolf = immediate win (1.0).
  * Otherwise an innocent is lost; at night the wolf freezes its loudest accuser
    among the remaining innocents.
  * Day 2: P0 votes again by renormalized belief over the survivors. Catching
    the wolf now scores 0.6 (two innocents already lost); missing scores 0.0.

For each candidate vote v we create `frontier/future/vote-v` — a REAL branch off
main — and capture INTO that branch: the plan gem, and a rollout gem whose
reasoning is the simulated timeline under each wolf-hypothesis, weighted by the
belief (EV computed mechanically). Each branch is then handed to a separate
agent that argues the case for its own future from inside it.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAY = ROOT.parent / "play"
sys.path.insert(0, str(ROOT))

from gemmery import (Action, DecisionBody, Gem, GitStore, IndexKeys,  # noqa: E402
                     KnowledgeBody, Kind, Provenance, TestSpec)

PLAYERS = ["P1", "P2", "P3", "P4"]
TS = 1_700_300_000

# the focal's actual round-1 belief from the played game
BELIEF = json.load(open(PLAY / "out" / "round1.json"))["belief"]
GAME = json.load(open(PLAY / "game.json"))
DAY1 = GAME["transcript"].split("--- Day 2 ---")[0].strip()

# who accused whom on day 1 (for the night-kill rule: wolf freezes its loudest accuser)
ACCUSED_BY = {"P2": ["P1"], "P0": ["P3"], "P1": ["P4"], "P4": []}


def accusers_of(w):
    return [a for tgt, accs in ACCUSED_BY.items() if tgt == w for a in accs]


def simulate(vote: str, wolf: str):
    """Roll the future of (vote, wolf-hypothesis). Returns (score, timeline)."""
    if vote == wolf:
        return 1.0, (f"Day 1: village follows P0 and eliminates {vote} — it WAS the "
                     f"wolf. Game over, all innocents alive. (score 1.0)")
    lines = [f"Day 1: village eliminates {vote} — innocent. The wolf ({wolf}) survives."]
    remaining = [p for p in PLAYERS if p not in (vote,)]
    # night: wolf freezes its loudest accuser still standing, else the top-believed rival
    accs = [a for a in accusers_of(wolf) if a in remaining and a != wolf]
    if accs:
        frozen = accs[0]
        lines.append(f"Night: {wolf} freezes {frozen} (its loudest accuser).")
    else:
        rivals = sorted((p for p in remaining if p != wolf),
                        key=lambda p: -BELIEF[p])
        frozen = rivals[0] if rivals else None
        if frozen:
            lines.append(f"Night: {wolf} freezes {frozen} (the biggest remaining threat).")
    survivors = [p for p in remaining if p != frozen]
    pool = {p: BELIEF[p] for p in survivors}
    pick = max(pool, key=pool.get)
    if pick == wolf:
        lines.append(f"Day 2: among {survivors}, renormalized belief points at "
                     f"{pick} — the wolf. Caught late. (score 0.6)")
        return 0.6, "\n".join(lines)
    lines.append(f"Day 2: among {survivors}, renormalized belief points at {pick} — "
                 f"innocent. The wolf ({wolf}) wins. (score 0.0)")
    return 0.0, "\n".join(lines)


def expected_value(vote):
    ev, parts = 0.0, []
    for w in PLAYERS:
        s, _ = simulate(vote, w)
        ev += BELIEF[w] * s
        parts.append((w, BELIEF[w], s))
    return ev, parts


def build():
    if (ROOT / "store").exists():
        shutil.rmtree(ROOT / "store")
    store = GitStore(ROOT / "store", actor="focal-P0")

    # main: the situation + belief (state before the fork)
    sit = Gem(kind=Kind.knowledge,
              provenance=Provenance("focal-P0", "futures", timestamp=TS),
              body=KnowledgeBody(
                  action=Action("frame_decision", {}),
                  reasoning=("Decision point after Day 1. Belief from memory "
                             f"(tell dossiers): {json.dumps(BELIEF)}. Day-1 "
                             f"statements:\n{DAY1}\n\nP0's vote is decisive; "
                             "wrong votes cost an innocent AND a night freeze."),
                  belief="pre-fork state"),
              index_keys=IndexKeys(action_type="decision_point", domain=["vote"]))
    store.capture(sit, path="decision/day1-vote/situation")

    branch_of, ev_of, tip_of = {}, {}, {}
    for i, v in enumerate(PLAYERS):
        br = store.branch_frontier(f"future/vote-{v}")
        branch_of[v] = br
        ev, parts = expected_value(v)
        ev_of[v] = ev
        plan = Gem(kind=Kind.decision,
                   provenance=Provenance("focal-P0", "futures", timestamp=TS + 10 + i),
                   body=DecisionBody(
                       action=Action("vote", {"target": v, "day": 1}),
                       reasoning=(f"IN THIS FUTURE we vote {v} on Day 1. Prior "
                                  f"P({v} is wolf) = {BELIEF[v]:.2f}."),
                       tests=[TestSpec("game_outcome", "play it out", "wolf caught")],
                       pre={"vote": v, "belief": BELIEF}),
                   index_keys=IndexKeys(action_type="vote", domain=[v]))
        store.capture(plan, branch=br, path=f"futures/vote-{v}/plan")

        tl = "\n\n".join(f"IF the wolf is {w} (P={pw:.2f}):\n{simulate(v, w)[1]}"
                         for w, pw, _ in parts)
        roll = Gem(kind=Kind.knowledge,
                   provenance=Provenance("focal-P0", "futures", timestamp=TS + 20 + i),
                   body=KnowledgeBody(
                       action=Action("simulate_future", {"vote": v}),
                       reasoning=(f"SIMULATED CONSEQUENCES of voting {v}.\n"
                                  f"Expected value = {ev:.3f}\n\n{tl}"),
                       belief=f"future of vote-{v}"),
                   index_keys=IndexKeys(action_type="rollout", domain=[v]))
        r = store.capture(roll, branch=br, path=f"futures/vote-{v}/rollout")
        tip_of[v] = r.sha

    json.dump({"belief": BELIEF, "branches": branch_of, "ev": ev_of,
               "tips": tip_of, "wolf": GAME["wolf"]},
              open(ROOT / "futures.json", "w"), indent=1)

    # one prompt per branch: the agent INHABITS that future only
    for v in PLAYERS:
        others = ", ".join(f"vote-{p}" for p in PLAYERS if p != v)
        rollout = store.read_file(f"futures/vote-{v}/rollout/reasoning.md",
                                  sha=tip_of[v]).decode()
        (ROOT / f"prompt_vote-{v}.txt").write_text(
            f"You are P0 in a Werewolf game, and in THIS branch of reality you "
            f"have committed to voting {v} on Day 1. You know only this future.\n\n"
            f"Day 1 statements:\n{DAY1}\n\n"
            f"Your belief (from tell dossiers): {json.dumps(BELIEF)}\n\n"
            f"{rollout}\n\n"
            "Assess YOUR OWN branch honestly from inside it: why WOULD a "
            "reasonable P0 choose this path — and what does it risk? Do not "
            f"compare to the other branches ({others}); argue this one on its "
            "merits. Return ONLY JSON: {\"stance\": \"endorse|caution|reject\", "
            "\"why_we_would\": \"2-3 sentences\", \"risks\": \"1-2 sentences\", "
            "\"confidence_0_1\": 0.0}\n")
    print("EVs:", {v: round(e, 3) for v, e in ev_of.items()})
    print("branches:", list(branch_of.values()))
    print("store gems:", store.count_commits())


if __name__ == "__main__":
    build()
