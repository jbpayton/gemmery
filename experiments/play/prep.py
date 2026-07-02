"""Set up the played-through Werewolf game — rich notes, real file system.

The memory is captured the way the schema intends, not as demo one-liners:
  * `history/<player>/game-NN`   — one observation gem per player per sampled
    past game (the raw evidence collection),
  * `knowledge/tells/<player>`   — a consolidated tell DOSSIER per player (full
    reasoning: baseline, wolf-tell, evidence counts, failure modes, what would
    change our mind), each `consumed`-linked to its underlying observations,
  * decisions land later at `decisions/round1`, `decisions/round2`.

Because the store now accumulates a real git file system, `git checkout` at any
sha materializes the whole memory as of that moment, and each commit's diff is
exactly the gem it added.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "werewolf"))
from engine import run_game, SCRIPTED  # noqa: E402

from gemmery import (Action, Cost, Gem, GitStore, IndexKeys, KnowledgeBody,  # noqa: E402
                     Kind, Provenance, TestSpec)

STORE = ROOT / "store"
TS = 1_700_100_000
N_HISTORY = 60
SAMPLE_PER_PLAYER = 6   # observation gems kept as raw evidence per player


def behavior(g, p):
    ss = [s for s in g.statements if s.speaker == p]
    bits = []
    for s in ss:
        if s.claims_seer:
            bits.append(f"claimed to be the Seer (vouching for {s.accuses})")
        elif s.silent:
            bits.append(f"stayed silent on day {s.round}")
        elif s.accuses:
            bits.append(f"accused {s.accuses} on day {s.round}")
    return "; ".join(bits) or "did nothing notable"


def tell_stats(games):
    st = {p: {"wolf": 0, "vil": 0, "seer_w": 0, "seer_v": 0, "accP0_w": 0,
              "accP0_v": 0, "silent1_w": 0, "silent1_v": 0, "accP1_w": 0,
              "accP1_v": 0, "accP2_v": 0} for p in SCRIPTED}
    for g in games:
        for p in SCRIPTED:
            w = (p == g.wolf); st[p]["wolf" if w else "vil"] += 1
            ss = [s for s in g.statements if s.speaker == p]
            if any(s.claims_seer for s in ss): st[p]["seer_w" if w else "seer_v"] += 1
            if any(s.accuses == "P0" and not s.claims_seer for s in ss): st[p]["accP0_w" if w else "accP0_v"] += 1
            if any(s.round == 1 and s.silent for s in ss): st[p]["silent1_w" if w else "silent1_v"] += 1
            if any(s.accuses == "P1" for s in ss): st[p]["accP1_w" if w else "accP1_v"] += 1
            if (not w) and any(s.accuses == "P2" for s in ss): st[p]["accP2_v"] += 1
    return st


def dossier(p, s):
    """A full tell dossier — the kind of note the schema is FOR."""
    common = (
        f"Sample: {s['wolf']} wolf-games, {s['vil']} villager-games observed.\n\n"
        "## Confidence and failure modes\n"
        "These are behavioral regularities, not laws. The counts above are the "
        "evidence base (see the consumed observation gems in history/). If the "
        "player ever behaves against baseline while confirmed innocent, this "
        "dossier must be revised — that is what the credit notes on this gem "
        "will track over time.\n\n"
        "## What would change our mind\n")
    if p == "P1":
        return (
            "# Tell dossier: P1\n\n"
            "## Baseline (as villager)\n"
            f"P1 holds a fixed grudge: it accuses P2 nearly every game it is "
            f"innocent ({s['accP2_v']}/{s['vil']} villager-games). It never "
            f"turned on P0 while innocent ({s['accP0_v']}/{s['vil']}).\n\n"
            "## Wolf tell\n"
            f"When P1 IS the wolf it abandons the grudge and attacks the focal "
            f"seat: accused P0 in {s['accP0_w']}/{s['wolf']} wolf-games. "
            "Interpretation: as a wolf it fears the strongest reader at the "
            "table and tries to eliminate P0 early.\n\n" + common +
            "- P1 accusing P0 while later confirmed innocent (breaks the tell).\n"
            "- P1 accusing anyone other than P2 while innocent (baseline drift).\n")
    if p == "P2":
        return (
            "# Tell dossier: P2  ⚠ THE TRAP\n\n"
            "## Baseline (as villager)\n"
            f"P2 is a lurker: silent both days in every innocent game observed "
            f"({s['vil']}/{s['vil']}). An innocent P2 volunteers nothing.\n\n"
            "## Wolf tell\n"
            f"When P2 IS the wolf it fakes authority: claimed to be the Seer in "
            f"{s['seer_w']}/{s['wolf']} wolf-games and 0/{s['vil']} villager-"
            "games, always 'clearing' a chosen player to steer suspicion.\n\n"
            "## Why this is dangerous\n"
            "A Seer claim is the most trust-inducing move in the game. A reader "
            "without this history would treat P2's claim as evidence of "
            "innocence and follow its steer — the claim is a weapon, not an "
            "alibi. The tell INVERTS the surface reading.\n\n" + common +
            "- P2 speaking at all while confirmed innocent.\n"
            "- A confirmed-innocent Seer claim from P2 (would break the tell "
            "completely and poison credit on this dossier).\n")
    if p == "P3":
        return (
            "# Tell dossier: P3\n\n"
            "## Baseline (as villager)\n"
            "P3 is a follower: it echoes the day's consensus accusation.\n\n"
            "## Wolf tell\n"
            f"When P3 IS the wolf it goes silent on Day 1 ({s['silent1_w']}/"
            f"{s['wolf']} wolf-games vs {s['silent1_v']}/{s['vil']} innocent) "
            "then counter-accuses whoever pointed at it.\n\n" + common +
            "- P3 silent on Day 1 while confirmed innocent.\n")
    return (
        "# Tell dossier: P4\n\n"
        "## Baseline (as villager)\n"
        f"P4 fixates on P1: accused P1 in {s['accP1_v']}/{s['vil']} innocent "
        "games — a near-invariant.\n\n"
        "## Wolf tell\n"
        f"When P4 IS the wolf the fixation vanishes ({s['accP1_w']}/{s['wolf']} "
        "wolf-games): it goes quiet, then bandwagons the leading accusation to "
        "blend in.\n\n" + common +
        "- P4 dropping the P1 fixation while confirmed innocent.\n")


def main():
    import shutil
    if STORE.exists():
        shutil.rmtree(STORE)
    store = GitStore(STORE, actor="focal-P0", email="p0@gemmery.local")
    games = [run_game(s) for s in range(N_HISTORY)]
    stats = tell_stats(games)

    # 1) raw evidence: per-player observation gems from sampled past games
    obs_sha = {p: [] for p in SCRIPTED}
    t = 0
    for p in SCRIPTED:
        wolf_games = [i for i, g in enumerate(games) if g.wolf == p][:SAMPLE_PER_PLAYER // 2]
        vil_games = [i for i, g in enumerate(games) if g.wolf != p][:SAMPLE_PER_PLAYER // 2]
        for i in sorted(wolf_games + vil_games):
            g = games[i]
            role = "WEREWOLF" if g.wolf == p else "villager"
            gem = Gem(kind=Kind.observation,
                      provenance=Provenance("focal-P0", "history", timestamp=TS + t),
                      body=__import__("gemmery").ObservationBody(
                          content=f"Game {i}: {p} was the {role}. That game {p} "
                                  f"{behavior(g, p)}. Full day-phase transcript "
                                  f"retained:\n{g.transcript()}"),
                      index_keys=IndexKeys(action_type="observation", domain=[p],
                                           precondition_shape=[role.lower(), f"g{i}"]))
            obs_sha[p].append(store.capture(gem, path=f"history/{p}/game-{i:02d}").sha)
            t += 1

    # 2) consolidated tell dossiers, each consuming its raw observations
    mem_sha = {}
    for j, p in enumerate(SCRIPTED):
        gem = Gem(kind=Kind.knowledge,
                  provenance=Provenance("focal-P0", "history", timestamp=TS + 100 + j),
                  body=KnowledgeBody(action=Action("consolidate_tell", {"player": p}),
                                     reasoning=dossier(p, stats[p]),
                                     belief=f"{p} behavioral signature",
                                     credence=0.9,
                                     tests=[TestSpec(f"tell::{p}", "future reveals",
                                                     "tell predicts role")]),
                  consumed=obs_sha[p],
                  index_keys=IndexKeys(action_type="tell", domain=[p],
                                       precondition_shape=["tell", p]))
        mem_sha[p] = store.capture(gem, path=f"knowledge/tells/{p}").sha

    # 3) the game to play (wolf = P2 -> the fake-Seer trap)
    seed = next(s for s in range(200) if run_game(s).wolf == "P2")
    game = run_game(seed)

    def day(n):
        return "\n".join("  " + s.render() for s in game.statements if s.round == n)

    mem_block = "\n".join(
        f"--- memory file knowledge/tells/{p} (id {mem_sha[p][:10]}) ---\n"
        f"{dossier(p, stats[p])}" for p in SCRIPTED)
    header = (
        "You are P0, a Villager in Werewolf. Exactly one of P1, P2, P3, P4 is the "
        "Werewolf. Your memory (a git file system of past games) contains a tell "
        "dossier per player:\n\n" + mem_block + "\n"
        "Decide who is most likely the Werewolf. Return ONLY JSON: "
        '{"guess":"Px","belief":{"P1":..,"P2":..,"P3":..,"P4":..},'
        '"used_memory":["Px",...],"reasoning":"one short paragraph"}\n\n')

    (ROOT / "prompt_round1.txt").write_text(header + "=== Day 1 ===\n" + day(1) + "\n")
    (ROOT / "prompt_round2.txt").write_text(
        header + "=== Day 1 ===\n" + day(1) + "\n\n=== Day 2 ===\n" + day(2) + "\n")
    json.dump({"seed": seed, "wolf": game.wolf, "mem_sha": mem_sha,
               "transcript": game.transcript()}, open(ROOT / "game.json", "w"), indent=1)

    print(f"store: {store.count_commits()} gems "
          f"({sum(len(v) for v in obs_sha.values())} observations + 4 dossiers)")
    print("memory file system at HEAD:\n")
    print(store.tree_listing(dirs_only=True))


if __name__ == "__main__":
    main()
