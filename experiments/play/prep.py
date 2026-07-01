"""Set up a played-through Werewolf game whose decisions we capture in git.

Builds a memory of each player's tell (as gems in a real GitStore), picks a game
where the wolf's fake-Seer claim would *trap* a memoryless reader, and writes the
per-round prompts the focal LLM will decide from. Later scripts capture the
focal's decisions as gems (with `consumed` edges to the memory it used), then git
is traversed post-hoc to explain why we played the way we did.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "werewolf"))
from engine import run_game, SCRIPTED, Statement  # noqa: E402

from gemmery import (Action, Cost, Gem, GitStore, IndexKeys, KnowledgeBody,  # noqa: E402
                     Kind, Provenance, TestSpec)

STORE = ROOT / "store"
TS = 1_700_100_000


def tell_stats(n=60):
    games = [run_game(s) for s in range(n)]
    st = {p: {"wolf": 0, "vil": 0, "seer_w": 0, "seer_v": 0, "accP0_w": 0,
              "accP0_v": 0, "silent1_w": 0, "silent1_v": 0, "accP1_w": 0, "accP1_v": 0}
          for p in SCRIPTED}
    for g in games:
        for p in SCRIPTED:
            w = (p == g.wolf); key = "wolf" if w else "vil"; st[p][key] += 1
            ss = [s for s in g.statements if s.speaker == p]
            if any(s.claims_seer for s in ss): st[p]["seer_w" if w else "seer_v"] += 1
            if any(s.accuses == "P0" and not s.claims_seer for s in ss): st[p]["accP0_w" if w else "accP0_v"] += 1
            if any(s.round == 1 and s.silent for s in ss): st[p]["silent1_w" if w else "silent1_v"] += 1
            if any(s.accuses == "P1" for s in ss): st[p]["accP1_w" if w else "accP1_v"] += 1
    return st


def tell_facts(st):
    f = {}
    f["P1"] = (f"P1's tell: as a villager P1 reliably accuses P2; when P1 is the wolf "
               f"it turns on P0 (the focal). Accused P0 in {st['P1']['accP0_w']}/"
               f"{st['P1']['wolf']} wolf-games vs {st['P1']['accP0_v']}/{st['P1']['vil']} "
               f"villager-games. => P1 accusing P0 signals wolf.")
    f["P2"] = (f"P2's tell: P2 stays SILENT as a villager, but fakes a Seer claim when "
               f"it is the wolf. Claimed Seer in {st['P2']['seer_w']}/{st['P2']['wolf']} "
               f"wolf-games vs {st['P2']['seer_v']}/{st['P2']['vil']} villager-games. "
               f"=> a Seer claim from P2 almost certainly means P2 is the wolf (it reads "
               f"as helpful, but it is the trap).")
    f["P3"] = (f"P3's tell: as a villager P3 follows the day's consensus; when wolf it "
               f"goes silent on Day 1 then counter-accuses. Silent Day 1 in "
               f"{st['P3']['silent1_w']}/{st['P3']['wolf']} wolf-games vs "
               f"{st['P3']['silent1_v']}/{st['P3']['vil']} villager-games.")
    f["P4"] = (f"P4's tell: as a villager P4 fixates on P1; when wolf it goes quiet then "
               f"bandwagons. Accused P1 in {st['P4']['accP1_w']}/{st['P4']['wolf']} "
               f"wolf-games vs {st['P4']['accP1_v']}/{st['P4']['vil']} villager-games.")
    return f


def main():
    import shutil
    if STORE.exists():
        shutil.rmtree(STORE)
    store = GitStore(STORE, actor="focal-P0", email="p0@gemmery.local")
    facts = tell_facts(tell_stats())

    # capture the memory (one tell gem per player) on a `memory` branch
    mem_sha = {}
    for i, p in enumerate(SCRIPTED):
        store.repo  # ensure init
        g = Gem(kind=Kind.knowledge,
                provenance=Provenance("focal-P0", "history", timestamp=TS + i),
                body=KnowledgeBody(action=Action("recall_tell", {"player": p}),
                                   reasoning=facts[p], belief=f"{p} behavioral tell",
                                   tests=[TestSpec(f"tell::{p}", "reveal", "confirmed")]),
                index_keys=IndexKeys(action_type="tell", domain=[p],
                                     precondition_shape=["tell", p]))
        mem_sha[p] = store.capture(g, branch="memory").sha

    # pick a game where the wolf is P2 -> the fake-Seer trap
    seed = next(s for s in range(200) if run_game(s).wolf == "P2")
    game = run_game(seed)

    def day(n):
        return "\n".join("  " + s.render() for s in game.statements if s.round == n)

    mem_block = "\n".join(f"  [{p} | id {mem_sha[p][:10]}] {facts[p]}" for p in SCRIPTED)
    header = (
        "You are P0, a Villager in Werewolf. Exactly one of P1, P2, P3, P4 is the "
        "Werewolf. You have MEMORY of each player's tell from past games:\n"
        f"{mem_block}\n\n"
        "Decide who is most likely the Werewolf. Return ONLY JSON: "
        '{{"guess":"Px","belief":{{"P1":0.._,"P2":..,"P3":..,"P4":..}},'
        '"used_memory":["Px",...],  # which players\' tells you actually relied on'
        '"reasoning":"one short paragraph"}}\n\n')

    (ROOT / "prompt_round1.txt").write_text(
        header + "=== Day 1 statements ===\n" + day(1) + "\n")
    (ROOT / "prompt_round2.txt").write_text(
        header + "=== Day 1 statements ===\n" + day(1) + "\n\n"
        "=== Day 2 statements ===\n" + day(2) + "\n")

    json.dump({"seed": seed, "wolf": game.wolf, "mem_sha": mem_sha,
               "transcript": game.transcript()},
              open(ROOT / "game.json", "w"), indent=1)
    print(f"game seed {seed}: wolf is {game.wolf} (fake-Seer trap). memory captured "
          f"({len(mem_sha)} tell gems). prompts written.")
    print("\n--- the game ---\n" + game.transcript())


if __name__ == "__main__":
    main()
