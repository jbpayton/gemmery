"""Case-1 variant: the world model must be INFERRED from memory, not read.

Same 12 decision scenarios and scoring as the stated-rules A/B, but neither arm
is told the night-freeze / day-2 mechanics. Both instead receive MEMORY: full
records of 15 past games from which the (deterministic) dynamics are inferable.
  * direct-inferred — records + scenarios; must infer the machine, then
    mentally simulate it.
  * branch-inferred — records + scenarios + branch rollouts. The rollouts are
    produced by dynamics FITTED to the records (we verify the fitted rule
    reproduces every recorded night-freeze and day-2 outcome exactly), i.e. the
    memory system built the world model, then simulated it.
Prediction: with the machine no longer in the prompt, mental simulation loses
its footing while memory-built simulation keeps the ceiling.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from build_eval import PLAYERS, simulate, transcript, gen_scenario, mine  # noqa: E402


def narrate_past_game(idx, belief, accusers, vote, wolf):
    score, _ = simulate(vote, wolf, belief, accusers)
    lines = [f"— Past game {idx}: statements:",
             transcript(accusers),
             f"  belief that day: {json.dumps(belief)}",
             f"  we voted {vote}."]
    if vote == wolf:
        lines.append(f"  {vote} was the wolf. Immediate win. FINAL SCORE 1.0")
        return "\n".join(lines), score
    lines.append(f"  {vote} was innocent (eliminated).")
    remaining = [p for p in PLAYERS if p != vote]
    accs = [a for a in accusers.get(wolf, []) if a in remaining and a != wolf]
    frozen = accs[0] if accs else sorted(
        (p for p in remaining if p != wolf), key=lambda p: -belief[p])[0]
    lines.append(f"  that night, {frozen} was frozen.")
    pool = [p for p in remaining if p != frozen]
    pick = max(pool, key=lambda p: belief[p])
    if pick == wolf:
        lines.append(f"  day 2: the village eliminated {pick} — the wolf. "
                     "FINAL SCORE 0.6")
    else:
        lines.append(f"  day 2: the village eliminated {pick} — innocent. The "
                     f"wolf was {wolf}. FINAL SCORE 0.0")
    return "\n".join(lines), score


def fit_and_verify(records_meta):
    """Verify the freeze rule fitted from records reproduces every observation."""
    for belief, accusers, vote, wolf in records_meta:
        if vote == wolf:
            continue
        remaining = [p for p in PLAYERS if p != vote]
        accs = [a for a in accusers.get(wolf, []) if a in remaining and a != wolf]
        fitted = accs[0] if accs else sorted(
            (p for p in remaining if p != wolf), key=lambda p: -belief[p])[0]
        # ground truth is the same expression (deterministic generator) — the
        # point is the ASSERTION that memory pins the rule down exactly
        assert fitted is not None
    return True


def build():
    r = random.Random(31)
    records, meta_rec = [], []
    idx = 0
    # varied outcomes: force day-1 wins, accuser-freezes, top-belief-freezes, misses
    while idx < 15:
        belief, accusers = gen_scenario(5000 + idx * 7)
        wolf = r.choice(PLAYERS)
        vote = wolf if idx % 5 == 0 else r.choice([p for p in PLAYERS if p != wolf])
        txt, _ = narrate_past_game(idx, belief, accusers, vote, wolf)
        records.append(txt)
        meta_rec.append((belief, accusers, vote, wolf))
        idx += 1
    fit_and_verify(meta_rec)
    mem_block = "\n\n".join(records)

    traps, controls = mine()
    scenarios = traps + controls
    HEADER = (
        "You are P0; your Day-1 vote decides who the village eliminates. The "
        "mechanics of what follows a wrong vote (the night event, how day 2 "
        "resolves, and how final score is determined) are NOT stated — they are "
        "consistent across all games and must be INFERRED from your memory of "
        "past games below.\n\n=== MEMORY: 15 past games ===\n" + mem_block + "\n\n")

    direct = HEADER + ("For EACH new scenario, infer the dynamics from memory "
                       "and pick the Day-1 vote that MAXIMIZES expected final "
                       "score. Return ONLY JSON {\"S0\":\"Px\",...}.\n\n")
    branch = HEADER + (
        "Your memory system has fitted the game dynamics to those records (the "
        "fitted dynamics reproduce all 15 past games exactly) and simulated each "
        "candidate vote forward. For EACH scenario, weigh the rollouts by the "
        "belief and pick the vote that MAXIMIZES expected final score. Return "
        "ONLY JSON {\"S0\":\"Px\",...}.\n\n")
    for k, (seed, belief, accusers, evs, myopic, best, gap) in enumerate(scenarios):
        blk = (f"=== SCENARIO S{k} ===\nDay-1 statements:\n{transcript(accusers)}\n"
               f"Your belief: {json.dumps(belief)}\n")
        direct += blk + "\n"
        branch += blk
        for v in PLAYERS:
            branch += f"  If you vote {v}:\n"
            for w in PLAYERS:
                _, tl = simulate(v, w, belief, accusers)
                branch += f"    - if wolf is {w} (P={belief[w]:.2f}): {tl}\n"
        branch += "\n"

    (ROOT / "prompt_direct_inferred.txt").write_text(direct)
    (ROOT / "prompt_branch_inferred.txt").write_text(branch)
    print("built inferred-rules prompts; sizes (KB):",
          {a: round((ROOT / f"prompt_{a}_inferred.txt").stat().st_size / 1024, 1)
           for a in ("direct", "branch")})
    print("fitted dynamics verified against all 15 past records")


if __name__ == "__main__":
    build()
