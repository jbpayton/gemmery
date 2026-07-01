"""End-to-end: git memory SERVES a multi-step plan; hypotheses tracked in git.

The integration the rest of the repo never ran, in the regime where it actually
bites. Advisors' reliability DRIFTS over a long career (some were great and have
since gone bad; some have come good). To plan well you need each advisor's
CURRENT reliability — a recency-filtered aggregate over a history far larger than
a context window — then you commit to a multi-step plan that relies on your pick.

Three arms differ only in the memory serving the model:
  * git      — recency-filtered exact aggregate from the columnar index (current
               reliability); candidate plans captured as gems on frontier
               branches, the chosen one cherry-picked to `main`, outcome credited.
  * markdown — a naive read of the notes.md slice that fits context = the OLDEST
               records (the top of the file) -> a STALE model.
  * none     — no model; act blind.

Reward = probability a T-step plan succeeds while relying on the chosen advisor
= current_reliability(pick) ** T. Multi-step reliance amplifies model error, so
this stacks every prior finding: structured recency aggregation (scale) + a
miscalibrated model makes deep plans worse than none (simulate).
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
K = 8
EPISODES = 40_000
RECENT = 3_000          # git's recency window
CONTEXT_SLICE = 5_000   # oldest records a naive context read holds


def make_world(seed=3):
    r = random.Random(seed)
    kinds = (["decliner"] * 3 + ["improver"] * 3 + ["stable"] * 2)
    r.shuffle(kinds)
    prof = {}
    for i, kind in enumerate(kinds):
        a = f"A{i}"
        if kind == "decliner":
            prof[a] = (r.uniform(0.82, 0.9), r.uniform(0.30, 0.40))   # great -> bad
        elif kind == "improver":
            prof[a] = (r.uniform(0.30, 0.40), r.uniform(0.82, 0.9))   # bad -> great
        else:
            prof[a] = (r.uniform(0.70, 0.78),) * 2                    # stable
    return prof


def rel_at(prof, a, e):
    s, en = prof[a]
    return s + (en - s) * (e / (EPISODES - 1))


def generate(prof, seed=4):
    r = random.Random(seed)
    recs = []                                # chronological (NOT shuffled)
    for e in range(EPISODES):
        for a in prof:
            recs.append((e, a, 1 if r.random() < rel_at(prof, a, e) else 0))
    return recs


def git_model(recs):
    """Current reliability: recency-filtered exact aggregate (columnar index)."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE rec(e INT, a TEXT, correct INT)")
    con.executemany("INSERT INTO rec VALUES(?,?,?)", recs)
    con.execute("CREATE INDEX i ON rec(e)")
    cut = EPISODES - RECENT
    rows = con.execute("SELECT a, AVG(correct) FROM rec WHERE e>=? GROUP BY a", (cut,))
    return {a: v for a, v in rows}


def markdown_model(recs):
    """Naive read of the oldest slice that fits context -> stale reliability."""
    agg = {}
    for e, a, c in recs[:CONTEXT_SLICE]:     # top of the file = oldest episodes
        s = agg.setdefault(a, [0, 0]); s[0] += c; s[1] += 1
    return {a: (s[0] / s[1] if s[1] else 0.5) for a, s in agg.items()}


def plan_reward(model, current, T):
    """Reward = P(T-step plan relying on the chosen advisor all succeed)."""
    if not model:
        return 0.5 ** T                       # no memory -> act blind each step
    pick = max(model, key=lambda a: model[a])
    if model[pick] <= 0.5:                     # model says nobody worth relying on
        return 0.5 ** T
    return current[pick] ** T                  # outcome paid by CURRENT reliability


def run():
    prof = make_world()
    recs = generate(prof)
    gm, mm = git_model(recs), markdown_model(recs)
    current = {a: rel_at(prof, a, EPISODES - 1) for a in prof}
    return prof, current, gm, mm, recs


if __name__ == "__main__":
    prof, current, gm, mm, recs = run()
    gpick, mpick = max(gm, key=gm.get), max(mm, key=mm.get)
    print(f"history: {len(recs):,} advisor-readings; a naive context read holds the "
          f"oldest ~{CONTEXT_SLICE/len(recs)*100:.1f}%.\n")
    print(f"git picks    {gpick}: model(recent)={gm[gpick]:.2f}, CURRENT reliability={current[gpick]:.2f}")
    print(f"markdown picks {mpick}: model(stale-old)={mm[mpick]:.2f}, CURRENT reliability={current[mpick]:.2f}")
    if current[mpick] < 0.5:
        print("  ^ markdown over-trusts a FALLEN advisor (great in the old records, bad now)\n")
    print("plan success probability vs plan length T (relying on the chosen advisor):")
    print(f"{'T':>4} | {'no memory':>10} | {'markdown-served':>15} | {'git-served (Gemmery)':>20}")
    for T in [1, 2, 4, 6, 8]:
        print(f"{T:>4} | {0.5**T:>10.3f} | {plan_reward(mm, current, T):>15.3f} "
              f"| {plan_reward(gm, current, T):>20.3f}")
