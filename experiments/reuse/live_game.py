"""The Long Table: one continuous session that rewards learning WHILE playing.

60 rounds of the decisive-vote game against the same recurring situations. The
night-freeze rule is unknown and must be learned from play — and at round 30
the opponent CHANGES its rule (drift). Every round: fit hypotheses from kept
records -> ensemble-plan (reusing kept rollout branches when valid) -> act ->
observe -> append the outcome to the store.

Drift handling is the retention machinery under load: when accumulated records
become inconsistent with EVERY hypothesis, the world has changed — the agent
drops oldest records until a consistent fit exists (windowed refit), and the
hypothesis-set change automatically invalidates stale rollout branches.

Baselines: NO-RETENTION (3 seed records forever, relearns nothing) and the
per-round ORACLE (plans with the true current rule).
"""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import reuse_demo as R  # noqa: E402

be = R.be
PLAYERS = R.PLAYERS
ROUNDS, DRIFT_AT = 60, 30
RULE_A, RULE_B = "accuser_else_topbelief", "topbelief_always"


def true_rule(step):
    return RULE_A if step < DRIFT_AT else RULE_B


def observe(vote, wolf, belief, accusers, step):
    if vote == wolf:
        return None
    rem = [p for p in PLAYERS if p != vote]
    return R.CANDS[true_rule(step)](rem, wolf, accusers, belief)


def true_ev_table(belief, accusers, step):
    rule = R.CANDS[true_rule(step)]
    return {v: sum(belief[w] * R.sim_with(rule, v, w, belief, accusers)
                   for w in PLAYERS) for v in PLAYERS}


def fit_windowed(records):
    """Fit; on total inconsistency (world changed), drop oldest until consistent."""
    recs = list(records)
    dropped = 0
    while True:
        surv = R.fit(recs)
        if surv or len(recs) <= 1:
            return surv or dict(R.CANDS), recs, dropped
        recs = recs[1:]
        dropped += 1


def run():
    traps, controls = be.mine()
    pool = [(f"S{k}", b, a) for k, (s, b, a, evs, m, best, g) in enumerate(traps)]
    rs = random.Random(8)
    seeds = []
    while len(seeds) < 3:
        b, a = be.gen_scenario(rs.randint(0, 99999))
        wolf = rs.choice(PLAYERS)
        vote = rs.choice([p for p in PLAYERS if p != wolf])
        fr = observe(vote, wolf, b, a, 0)
        rem = [p for p in PLAYERS if p != vote]
        # keep only NON-discriminating seeds (ambiguity must be learned away in play)
        if fr and R.CANDS["topbelief_always"](rem, wolf, a, b) == fr:
            seeds.append((b, a, vote, wolf, fr))

    rng = random.Random(99)
    records = list(seeds)
    cache = {}
    hist = {k: [] for k in ("ev", "ev_fresh", "ev_oracle", "hyp", "records",
                            "branches", "cache_hit", "window_drops")}
    for step in range(ROUNDS):
        sid, belief, accusers = pool[step % len(pool)]
        truth_table = true_ev_table(belief, accusers, step)
        opt = max(truth_table.values())

        # --- persistent agent (retention + windowed refit + branch reuse) ---
        surv, recs_used, dropped = fit_windowed(records)
        records = recs_used if dropped else records
        key = (sid, frozenset(surv))
        if key in cache:
            table = cache[key]
            hist["cache_hit"].append(1)
        else:
            table = {v: sum(sum(belief[w] * R.sim_with(r, v, w, belief, accusers)
                                for w in PLAYERS) for r in surv.values()) / len(surv)
                     for v in PLAYERS}
            cache[key] = table
            hist["cache_hit"].append(0)
        pick = max(table, key=table.get)
        hist["ev"].append(truth_table[pick] / opt)          # fraction of optimal
        hist["hyp"].append(len(surv))
        hist["records"].append(len(records))
        hist["branches"].append(len(cache))
        hist["window_drops"].append(dropped)

        # --- no-retention baseline (seeds forever) ---
        surv0 = R.fit(seeds) or dict(R.CANDS)
        t0 = {v: sum(sum(belief[w] * R.sim_with(r, v, w, belief, accusers)
                         for w in PLAYERS) for r in surv0.values()) / len(surv0)
              for v in PLAYERS}
        hist["ev_fresh"].append(truth_table[max(t0, key=t0.get)] / opt)
        hist["ev_oracle"].append(1.0)

        # --- the world happens; the outcome is RETAINED ---
        wolf = rng.choices(PLAYERS, weights=[belief[p] for p in PLAYERS])[0]
        fr = observe(pick, wolf, belief, accusers, step)
        records.append((belief, accusers, pick, wolf, fr))

    json.dump(hist, open(ROOT / "live_game.json", "w"), indent=1)
    return hist


if __name__ == "__main__":
    h = run()
    import numpy as np
    q = ROUNDS // 4
    print(f"fraction-of-optimal EV: rounds 0-14={np.mean(h['ev'][:15]):.3f}  "
          f"15-29={np.mean(h['ev'][15:30]):.3f}  "
          f"30-44 (post-drift)={np.mean(h['ev'][30:45]):.3f}  "
          f"45-59={np.mean(h['ev'][45:]):.3f}")
    print(f"no-retention baseline:  {np.mean(h['ev_fresh']):.3f} throughout")
    print(f"hypotheses: start {h['hyp'][0]} -> pre-drift {h['hyp'][29]} -> "
          f"at drift {h['hyp'][30:33]} -> end {h['hyp'][-1]}")
    print(f"records kept: {h['records'][-1]}; kept branch tables: {h['branches'][-1]}; "
          f"cache hits: {sum(h['cache_hit'])}/{ROUNDS}; "
          f"window drops at drift: {max(h['window_drops'])}")
