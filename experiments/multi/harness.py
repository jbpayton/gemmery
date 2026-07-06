"""Multi-agent shared memory (spec 13): conflict surfacing, branches as
perspectives, adjudicated merge.

The distributed-detective game: K hidden binary facts; N agents each observe
noisy random subsets per round with UNEQUAL, UNKNOWN reliabilities. Each round
one fresh fact is queried, the team answers (per arm), truth is revealed, and
every agent that had a claim gets a walk-forward credit update.

Arms:
  solo    - majority vote of agents' private claims (no shared memory)
  naive   - one shared slot per fact, LAST WRITE WINS (what a shared .md is)
  adjud   - conflicts SURFACED (agents' claims differ), resolved by EARNED
            credit (beta-posterior on each agent's revealed track record)
  oracle  - true-reliability log-odds weighting (ceiling)

Pre-registered: on non-conflicted queries all sharing arms agree; the
headroom is exactly the conflicted cell, and adjudication only separates
from naive once credit has accumulated (early rounds ~ tied).
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
K, N, T, M = 90, 4, 90, 6
RELS = [0.92, 0.80, 0.68, 0.55]


def run_seed(seed):
    rng = random.Random(seed)
    truth = [rng.random() < 0.5 for _ in range(K)]
    obs = [[[] for _ in range(K)] for _ in range(N)]       # per agent per fact
    last_write = [None] * K                                 # naive shared slot
    credit = [[0, 0] for _ in range(N)]                     # [correct, total]
    order = list(range(K)); rng.shuffle(order)
    rows = []
    for t in range(T):
        # --- observations ---
        for i in range(N):
            for k in rng.sample(range(K), M):
                seen = truth[k] if rng.random() < RELS[i] else not truth[k]
                obs[i][k].append(seen)
                last_write[k] = (i, seen)                   # naive: clobber
        # --- claims: each agent's majority over its own observations ---
        q = order[t]
        claims = {}
        for i in range(N):
            if obs[i][q]:
                claims[i] = sum(obs[i][q]) * 2 > len(obs[i][q]) or \
                            (sum(obs[i][q]) * 2 == len(obs[i][q]) and obs[i][q][-1])
        row = {"t": t, "n_claims": len(claims)}
        if not claims:
            rows.append(row); continue
        vals = set(claims.values())
        row["conflict"] = len(vals) > 1
        # solo: unweighted majority
        up = sum(1 for v in claims.values() if v)
        row["solo"] = (up * 2 > len(claims)) or (up * 2 == len(claims))
        # naive: last write wins
        row["naive"] = last_write[q][1] if last_write[q] else row["solo"]
        # adjudicated: earned-credit weighted vote (log-odds of beta mean)
        def vote(weight_fn):
            s = 0.0
            for i, v in claims.items():
                w = weight_fn(i)
                s += math.log(w / (1 - w)) * (1 if v else -1)
            return s > 0 or abs(s) <= 1e-12
        # adjudication triggers ON surfaced conflict; unanimity passes through
        if not row["conflict"]:
            row["adjud"] = row["oracle"] = next(iter(vals))
        else:
            row["adjud"] = vote(lambda i: min(max((credit[i][0] + 1) / (credit[i][1] + 2), 0.02), 0.98))
            row["oracle"] = vote(lambda i: RELS[i])
        # --- reveal + walk-forward credit ---
        for i, v in claims.items():
            credit[i][1] += 1
            credit[i][0] += (v == truth[q])
        for a in ("solo", "naive", "adjud", "oracle"):
            row[a] = (row[a] == truth[q])
        rows.append(row)
    return rows


def main():
    seeds = 30
    allrows = []
    for s in range(seeds):
        for r in run_seed(s):
            r["seed"] = s; allrows.append(r)
    arms = ("solo", "naive", "adjud", "oracle")
    scored = [r for r in allrows if "solo" in r]

    def acc(rows, a):
        return sum(r[a] for r in rows) / len(rows) if rows else float("nan")

    print(f"{seeds} seeds x {T} queries; {len(scored)} scored "
          f"({sum(r['conflict'] for r in scored)} conflicted = "
          f"{sum(r['conflict'] for r in scored)/len(scored):.0%})\n")
    print(f"{'arm':8s} {'overall':>8s} {'rounds 1-30':>12s} {'31-60':>7s} {'61-90':>7s} "
          f"{'conflicted':>11s} {'clean':>7s}")
    out = {}
    for a in arms:
        thirds = [acc([r for r in scored if lo <= r['t'] < hi], a)
                  for lo, hi in ((0, 30), (30, 60), (60, 90))]
        conf = acc([r for r in scored if r["conflict"]], a)
        clean = acc([r for r in scored if not r["conflict"]], a)
        o = acc(scored, a)
        out[a] = {"overall": o, "thirds": thirds, "conflicted": conf, "clean": clean}
        print(f"{a:8s} {o:8.3f} {thirds[0]:12.3f} {thirds[1]:7.3f} {thirds[2]:7.3f} "
              f"{conf:11.3f} {clean:7.3f}")
    # paired bootstrap: adjud vs naive on conflicted queries
    conf_rows = [r for r in scored if r["conflict"]]
    rng = random.Random(0)
    deltas = []
    for _ in range(2000):
        smp = [conf_rows[rng.randrange(len(conf_rows))] for _ in range(len(conf_rows))]
        deltas.append(acc(smp, "adjud") - acc(smp, "naive"))
    deltas.sort()
    print(f"\nadjud - naive on conflicts: +{out['adjud']['conflicted']-out['naive']['conflicted']:.3f} "
          f"[95% CI {deltas[50]:+.3f}, {deltas[1949]:+.3f}]")
    json.dump(out, open(ROOT / "results.json", "w"), indent=1)


if __name__ == "__main__":
    main()
