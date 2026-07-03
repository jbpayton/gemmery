"""Does KEEPING alternate-reality branches across runs speed the learning curve?

Sequential episodes against the same recurring situations (the futures_eval
game, dynamics unknown). Two agents, identical planner (fit rule hypotheses
from records -> ensemble-plan over survivors -> argmax EV):

  * FRESH      — wipes its store between episodes: forever re-fits from the same
                 3 seed records (ambiguity never shrinks) and re-simulates every
                 rollout every episode (no kept branches).
  * PERSISTENT — the gemmery discipline: every executed episode's full outcome
                 (including the observed night-freeze) is appended to the store;
                 rollout branches are KEPT and reused whenever the same situation
                 recurs under the same surviving-hypothesis set.

Measured per episode: planning quality (true EV of picks over the situation
pool), # surviving rule-hypotheses (ambiguity), and rollouts computed vs served
from kept branches (compute saved).
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FE = ROOT.parent / "futures_eval"


def load_mod(name, p):
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    sys.path.insert(0, str(Path(p).parent))
    spec.loader.exec_module(m)
    sys.path.pop(0)
    return m


be = load_mod("r_be", FE / "build_eval.py")
PLAYERS = be.PLAYERS

# rule-hypothesis space (structured, fitted against observed freezes)
CANDS = {
    "accuser_else_topbelief": lambda rem, wolf, acc, bel:
        ([a for a in acc.get(wolf, []) if a in rem and a != wolf] or
         [sorted((p for p in rem if p != wolf), key=lambda p: -bel[p])[0]])[0],
    "topbelief_always": lambda rem, wolf, acc, bel:
        sorted((p for p in rem if p != wolf), key=lambda p: -bel[p])[0],
    "accuser_else_lowbelief": lambda rem, wolf, acc, bel:
        ([a for a in acc.get(wolf, []) if a in rem and a != wolf] or
         [sorted((p for p in rem if p != wolf), key=lambda p: bel[p])[0]])[0],
    "lowbelief_always": lambda rem, wolf, acc, bel:
        sorted((p for p in rem if p != wolf), key=lambda p: bel[p])[0],
}
TRUE = "accuser_else_topbelief"


def observe(vote, wolf, belief, accusers):
    """Execute in the real world; return the observed freeze (None if day-1 win)."""
    if vote == wolf:
        return None
    rem = [p for p in PLAYERS if p != vote]
    return CANDS[TRUE](rem, wolf, accusers, belief)


def fit(records):
    surviving = dict(CANDS)
    for belief, accusers, vote, wolf, frozen in records:
        if frozen is None:
            continue
        rem = [p for p in PLAYERS if p != vote]
        for name in list(surviving):
            if surviving[name](rem, wolf, accusers, belief) != frozen:
                del surviving[name]
    return surviving


def sim_with(rule, vote, wolf, belief, accusers):
    if vote == wolf:
        return 1.0
    rem = [p for p in PLAYERS if p != vote]
    frozen = rule(rem, wolf, accusers, belief)
    pool = [p for p in rem if p != frozen]
    return 0.6 if max(pool, key=lambda p: belief[p]) == wolf else 0.0


def run():
    # recurring situation pool: the 8 trap scenarios (where planning quality shows)
    traps, controls = be.mine()
    pool = [(f"S{k}", belief, accusers, evs, best)
            for k, (seed, belief, accusers, evs, myopic, best, gap) in enumerate(traps)]

    # seed records: 3 games none of which discriminate accuser- vs topbelief-freeze
    seeds = []
    rs = random.Random(8)
    while len(seeds) < 3:
        belief, accusers = be.gen_scenario(rs.randint(0, 99999))
        wolf = rs.choice(PLAYERS)
        vote = rs.choice([p for p in PLAYERS if p != wolf])
        fr = observe(vote, wolf, belief, accusers)
        rem = [p for p in PLAYERS if p != vote]
        if fr and CANDS["topbelief_always"](rem, wolf, accusers, belief) == fr:
            seeds.append((belief, accusers, vote, wolf, fr))  # non-discriminating
    assert len(fit(seeds)) >= 2

    EPISODES = 24
    rng = random.Random(99)
    curves = {a: {"ev": [], "hyp": [], "sims": [], "cached": []}
              for a in ("fresh", "persistent")}
    records_p = list(seeds)
    branch_cache = {}          # (sid, frozenset(hyp-names)) -> EV table (kept branches)
    cum = {"fresh": 0, "persistent": 0}

    for ep in range(EPISODES):
        sid, belief, accusers, evs, best = pool[ep % len(pool)]
        for arm in ("fresh", "persistent"):
            recs = seeds if arm == "fresh" else records_p
            surv = fit(recs)
            key = (sid, frozenset(surv))
            if arm == "persistent" and key in branch_cache:
                table = branch_cache[key]
                sims = 0
                curves[arm]["cached"].append(1)
            else:
                table = {v: sum(sum(belief[w] * sim_with(r, v, w, belief, accusers)
                                    for w in PLAYERS) for r in surv.values()) / len(surv)
                         for v in PLAYERS}
                sims = len(PLAYERS) * len(PLAYERS) * len(surv)
                curves[arm]["cached"].append(0)
                if arm == "persistent":
                    branch_cache[key] = table
            cum[arm] += sims
            pick = max(table, key=table.get)
            curves[arm]["ev"].append(evs[pick])
            curves[arm]["hyp"].append(len(surv))
            curves[arm]["sims"].append(cum[arm])

        # the world happens once; PERSISTENT keeps the outcome
        wolf = rng.choices(PLAYERS, weights=[belief[p] for p in PLAYERS])[0]
        pick_p = max(branch_cache[(sid, frozenset(fit(records_p)))],
                     key=branch_cache[(sid, frozenset(fit(records_p)))].get)
        fr = observe(pick_p, wolf, belief, accusers)
        records_p.append((belief, accusers, pick_p, wolf, fr))

    json.dump(curves, open(ROOT / "curves.json", "w"), indent=1)
    return curves


if __name__ == "__main__":
    c = run()
    n = len(c["fresh"]["ev"])
    half = n // 2
    print(f"{'':14s} {'EV(first half)':>15s} {'EV(second half)':>16s} "
          f"{'hyp@end':>8s} {'total sims':>11s} {'cache hits':>10s}")
    for a in ("fresh", "persistent"):
        e = c[a]
        print(f"{a:14s} {sum(e['ev'][:half])/half:>15.3f} "
              f"{sum(e['ev'][half:])/(n-half):>16.3f} {e['hyp'][-1]:>8d} "
              f"{e['sims'][-1]:>11d} {sum(e['cached'])}/{n:>3d}")
    print(f"\noptimal-policy EV on this pool: "
          f"{sum(be.mine()[0][k][3][be.mine()[0][k][5]] for k in range(8))/8:.3f}")
