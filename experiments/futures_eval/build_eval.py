"""Does branch-simulation IN the reasoning improve gameplay? (A/B, matched info)

Scenario: the Day-1 decisive-vote werewolf endgame from experiments/futures,
generalized. Rules (given identically to both arms):
  * Vote the wolf on Day 1 -> clean win (1.0).
  * Vote an innocent -> that innocent is gone; at night the wolf freezes its
    first surviving Day-1 accuser, else the highest-belief survivor that isn't
    itself; Day 2 the village votes the highest-belief survivor: catching the
    wolf late scores 0.6, missing scores 0.0.

We mine scenarios where the myopic move (vote the top suspect) is NOT the
EV-best move — traps where night-freeze dynamics make the second suspect or a
protective vote better — plus controls where myopic is right. Arms:
  * direct  — situation + belief + rules. May simulate mentally.
  * branch  — same, PLUS the branch apparatus' product: per-candidate simulated
    timelines per wolf-hypothesis (no aggregated EVs — the agent must weigh).
Score = true EV of the chosen vote; also optimal-pick rate. Mechanical
baselines: argmax-belief, random, EV-optimal ceiling.
"""
from __future__ import annotations

import itertools
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAYERS = ["P1", "P2", "P3", "P4"]


def simulate(vote, wolf, belief, accusers):
    """Roll (vote, wolf-hypothesis) forward. Returns (score, timeline)."""
    if vote == wolf:
        return 1.0, f"eliminate {vote} = the wolf. Clean Day-1 win (1.0)."
    lines = [f"eliminate {vote} (innocent); wolf {wolf} survives."]
    remaining = [p for p in PLAYERS if p != vote]
    accs = [a for a in accusers.get(wolf, []) if a in remaining and a != wolf]
    if accs:
        frozen = accs[0]
        lines.append(f"night: {wolf} freezes {frozen} (its accuser).")
    else:
        rivals = sorted((p for p in remaining if p != wolf), key=lambda p: -belief[p])
        frozen = rivals[0] if rivals else None
        lines.append(f"night: {wolf} freezes {frozen} (top remaining threat).")
    pool = [p for p in remaining if p != frozen]
    pick = max(pool, key=lambda p: belief[p])
    if pick == wolf:
        lines.append(f"day 2: pool {pool}, belief points at {pick} = wolf. Late catch (0.6).")
        return 0.6, " ".join(lines)
    lines.append(f"day 2: pool {pool}, belief points at {pick} (innocent). Wolf wins (0.0).")
    return 0.0, " ".join(lines)


def ev_table(belief, accusers):
    return {v: sum(belief[w] * simulate(v, w, belief, accusers)[0] for w in PLAYERS)
            for v in PLAYERS}


def gen_scenario(seed):
    r = random.Random(seed)
    raw = [r.uniform(0.5, 3.0) for _ in PLAYERS]
    s = sum(raw)
    belief = {p: round(x / s, 2) for p, x in zip(PLAYERS, raw)}
    belief[PLAYERS[0]] = round(1 - sum(belief[p] for p in PLAYERS[1:]), 2)
    accusers = {}
    for p in PLAYERS:  # each player accuses someone (or stays silent)
        if r.random() < 0.75:
            tgt = r.choice([q for q in PLAYERS if q != p])
            accusers.setdefault(tgt, []).append(p)
    return belief, accusers


def transcript(accusers):
    lines = []
    for p in PLAYERS:
        said = [t for t, accs in accusers.items() if p in accs]
        lines.append(f'  {p}: "{f"I think {said[0]} is the werewolf." if said else "(stays silent)"}"')
    return "\n".join(lines)


RULES = (
    "RULES: You are P0; your Day-1 vote is decisive. If you vote the wolf, clean "
    "win (score 1.0). If you vote an innocent: that innocent is eliminated; at "
    "night the wolf freezes its first surviving Day-1 accuser (or, if none, the "
    "highest-belief survivor other than itself); on Day 2 the village eliminates "
    "the highest-belief survivor — catching the wolf late scores 0.6, missing "
    "scores 0.0. Your belief distribution is given and is trustworthy.\n")


def mine():
    traps, controls = [], []
    for seed in range(4000):
        belief, accusers = gen_scenario(seed)
        evs = ev_table(belief, accusers)
        myopic = max(PLAYERS, key=lambda p: belief[p])
        best = max(PLAYERS, key=lambda p: evs[p])
        gap = evs[best] - evs[myopic]
        spread = belief[myopic] - sorted(belief.values())[-2]
        if best != myopic and gap >= 0.08 and len(traps) < 8:
            traps.append((seed, belief, accusers, evs, myopic, best, gap))
        elif best == myopic and spread <= 0.15 and len(controls) < 4:
            controls.append((seed, belief, accusers, evs, myopic, best, 0.0))
        if len(traps) >= 8 and len(controls) >= 4:
            break
    return traps, controls


def build():
    traps, controls = mine()
    scenarios = traps + controls
    print(f"mined {len(traps)} traps + {len(controls)} controls "
          f"(trap EV gaps: {[round(t[6], 2) for t in traps]})")

    meta, direct, branch = {}, RULES + "\n", RULES + "\n"
    direct += ("For EACH scenario pick your Day-1 vote to MAXIMIZE expected "
               "score. Think it through. Return ONLY JSON {\"S0\":\"Px\",...}.\n\n")
    branch += ("For EACH scenario you are ALSO given simulated branch rollouts — "
               "one per candidate vote, rolled forward under each wolf hypothesis "
               "(these follow mechanically from the rules). Weigh them by your "
               "belief and pick the vote that MAXIMIZES expected score. Return "
               "ONLY JSON {\"S0\":\"Px\",...}.\n\n")
    for k, (seed, belief, accusers, evs, myopic, best, gap) in enumerate(scenarios):
        sid = f"S{k}"
        meta[sid] = {"belief": belief, "evs": evs, "myopic": myopic,
                     "best": best, "trap": best != myopic}
        blk = (f"=== SCENARIO {sid} ===\nDay-1 statements:\n{transcript(accusers)}\n"
               f"Your belief: {json.dumps(belief)}\n")
        direct += blk + "\n"
        branch += blk
        for v in PLAYERS:
            branch += f"  If you vote {v}:\n"
            for w in PLAYERS:
                _, tl = simulate(v, w, belief, accusers)
                branch += f"    - if wolf is {w} (P={belief[w]:.2f}): {tl}\n"
        branch += "\n"

    (ROOT / "prompt_direct.txt").write_text(direct)
    (ROOT / "prompt_branch.txt").write_text(branch)
    json.dump(meta, open(ROOT / "meta.json", "w"), indent=1)

    # mechanical baselines
    n = len(scenarios)
    base = {"argmax_belief": 0.0, "random": 0.0, "ev_optimal": 0.0}
    for sid, m in meta.items():
        base["argmax_belief"] += m["evs"][m["myopic"]] / n
        base["random"] += sum(m["evs"].values()) / 4 / n
        base["ev_optimal"] += m["evs"][m["best"]] / n
    json.dump(base, open(ROOT / "baselines.json", "w"), indent=1)
    print("baselines:", {k: round(v, 3) for k, v in base.items()})
    print("prompt sizes (KB):",
          {a: round((ROOT / f'prompt_{a}.txt').stat().st_size / 1024, 1)
           for a in ("direct", "branch")})


if __name__ == "__main__":
    build()
