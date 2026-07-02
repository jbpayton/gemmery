"""Fill the master matrix's unmeasured cells with seeded deterministic runs.

Definitions per column, held consistent:
  vector  — profiles/estimates built from top-k SIMILAR retrieved records
            (a sample), never full counts, never recency-aware.
  exact   — full/windowed COUNT aggregates (the columnar layer).
  flat    — read/grep raw records with no machinery (exact-string match or a
            casual read; no counting infrastructure).
"""
from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
EXP = ROOT.parent


def load_mod(name, relpath):
    p = EXP / relpath
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m  # dataclasses looks the module up in sys.modules
    sys.path.insert(0, str(p.parent))
    spec.loader.exec_module(m)
    sys.path.pop(0)
    return m


out = {}

# ---- R1 werewolf: vector & exact detectors (200 games) ---------------------
ww = load_mod("g_ww", "werewolf/engine.py")
rng = random.Random(99)
games = [ww.run_game(s) for s in range(200)]


def ww_feats(g):
    return {(s.speaker,
             "seer" if s.claims_seer else ("silent" if s.silent else "acc"),
             s.accuses) for s in g.statements}


ex_ok = vec_ok = 0
for i, g in enumerate(games):
    past = games[:i]
    ex_ok += ww.memory_detector(g, ww.build_profiles(past), rng) == g.wolf
    if past:
        f = ww_feats(g)
        sims = sorted(past, key=lambda h: -len(f & ww_feats(h)))[:20]
        vec_ok += ww.memory_detector(g, ww.build_profiles(sims), rng) == g.wolf
out["R1"] = {"exact": round(ex_ok / 200, 2), "vector": round(vec_ok / 199, 2)}

# ---- R2 gnosia: vector & exact detectors (300 games) ------------------------
gn = load_mod("g_gn", "gnosia/engine.py")
pool = gn.make_pool(24)
rng2 = random.Random(7)
ggames = [gn.run_game(s, pool, 8, 2) for s in range(300)]


def gn_feats(g):
    return {(s.speaker, s.claim_role.value if s.claim_role else "acc", s.accuse)
            for s in g.statements}


ex_ok = vec_ok = 0
for i, g in enumerate(ggames):
    past = ggames[:i]
    ex_ok += gn.memory_detector(g, gn.build_profiles(past), rng2) in g.gnosia_set()
    if past:
        f = gn_feats(g)
        sims = sorted(past, key=lambda h: -len(f & gn_feats(h)))[:20]
        vec_ok += gn.memory_detector(g, gn.build_profiles(sims), rng2) in g.gnosia_set()
out["R2"] = {"exact": round(ex_ok / 300, 2), "vector": round(vec_ok / 299, 2)}

# ---- R5 complex rule: flat = grep the exact situation (== exact-cell) -------
cr = load_mod("g_cr", "complex_rules/rules_demo.py")
vals = [cr.evaluate(s)["exact_cell_conditional"] for s in range(8)]
out["R5"] = {"flat": round(float(np.mean(vals)), 2)}

# ---- R6 drift: exact (recency window) & vector (similar, no recency) on the
#      SAME 8 LLM test games -------------------------------------------------
dr = load_mod("g_dr", "drift/build.py")
rngh = random.Random(4)
hist = [dr.gen_game(i, rngh) for i in range(dr.N_HIST)]
trng = random.Random(77)
spec = [("P4", True), ("P1", True), ("P2", None), ("P3", True),
        ("P1", False), ("P2", None), ("P4", None), ("P3", False)]
tests = []
for k, (w, hide) in enumerate(spec):
    g = dr.gen_game(900 + k, trng, phase="B", wolf=w)
    if hide is not None and w != "P2":
        t = dr.tells("B")
        g["behavior"][w] = t[w]["vil" if hide else "wolf"]
    tests.append(g)
rngd = random.Random(5)
ex_ok = vec_ok = 0
for t in tests:
    ex_ok += dr.detect(t, dr.profile(hist, dr.WINDOW), rngd) == t["wolf"]
    f = set(t["behavior"].items())
    sims = sorted(hist, key=lambda h: -len(f & set(h["behavior"].items())))[:15]
    vec_ok += dr.detect(t, dr.profile(sims), rngd) == t["wolf"]
out["R6"] = {"exact": round(ex_ok / 8, 2), "vector": round(vec_ok / 8, 2)}

# ---- R7 POMDP: exact = calibrated (full track record) = good model;
#      vector = q estimated from a k=25 retrieved sample per episode ----------
sim = load_mod("g_sim", "simulate/simulate_demo.py")
h = max(sim.HORIZONS)
out["R7"] = {"exact": round(sim.sweep(0.9, 0.9)[h], 2)}
rs = random.Random(42)
tot = 0.0
N = 4000
for i in range(N):
    q_est = sum(rs.random() < 0.9 for _ in range(25)) / 25   # sampled calibration
    tot += sim.run_episode(h, q_est, random.Random(1000 + i), 0.9)
out["R7"]["vector"] = round(tot / N, 2)

# ---- R8 planning-from-memory: vector = reliability from a uniform k=200
#      sample of each advisor's records (mixed eras, no recency) --------------
integ = load_mod("g_int", "integrated/integrated_demo.py")
prof, current, gm, mm, recs = integ.run()
rsam = random.Random(11)
by_adv = {}
for e, a, c in recs:
    by_adv.setdefault(a, []).append(c)
vec_model = {a: float(np.mean(rsam.sample(v, 200))) for a, v in by_adv.items()}
out["R8"] = {"vector": round(integ.plan_reward(vec_model, current, 6), 3)}

print("computed fills:")
for r, cells in out.items():
    print(f"  {r}: {cells}")
