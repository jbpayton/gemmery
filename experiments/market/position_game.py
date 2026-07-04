"""Position-sizing on real data: does SIMULATION over memory-fitted dynamics
beat myopic signal-chasing once decisions have consequences (transaction costs)?

State per (symbol, day): position w in {-1,0,+1}. Reward: w*r_next - c*|dw|.
The belief p(up) comes from the SAME walk-forward credit dossiers as before.
World model (fitted walk-forward, pooled): E[r | belief-bucket] and the bucket
Markov transition matrix — exact aggregates over the whole record. Policies:
  naive   — chase the signal: w = sign(p-0.5) when confident, ignore costs.
  greedy  — 1-step cost-aware argmax (today's edge minus today's cost).
  planner — H-step backward induction over the fitted bucket-MDP (simulation).
All share identical beliefs and fitted stats; only the horizon differs.
"""
from __future__ import annotations
import csv, json, math
from collections import defaultdict, deque
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from scale_backtest import load_news, load_price, logit

BUCKETS = [-0.03, -0.015, -0.005, 0.005, 0.015, 0.03]  # edges on (p-0.5)
NB = len(BUCKETS) + 1
H = 10

def bucket(p):
    d = p - 0.5
    for i, e in enumerate(BUCKETS):
        if d < e: return i
    return NB - 1

def build_stream():
    news = load_news()
    syms = sorted(set(s for s, _ in news.keys()))
    prior = 0.507
    doss = defaultdict(lambda: [0.0, 0.0])
    GAMMA, last_day = 0.997, None
    stream = []  # (day, sym, p, r_next)
    per_sym = {}
    for sym in syms:
        pr = load_price(sym)
        ratios = [(d1, c1/c0 - 1) for (d0,c0),(d1,c1) in zip(pr, pr[1:])]
        per_sym[sym] = ratios
    # merge chronologically
    events = []
    for sym, ratios in per_sym.items():
        trail = deque(maxlen=20)
        for i in range(1, len(ratios)):
            d, r = ratios[i]
            d_prev = ratios[i-1][0]
            n_tw, sent = news.get((sym, d_prev), (0, 0))
            avg = (sum(trail)/len(trail)) if trail else 0.0
            trail.append(n_tw)
            if d < "2010-01-01": continue
            r1 = ratios[i-1][1]
            r5 = sum(x[1] for x in ratios[max(0,i-5):i])/min(5,i)
            fired = []
            if r1 > 0: fired.append("mom1_up")
            if r1 <= -0.015: fired.append("big_drop_reversal")
            if r5 > 0: fired.append("mom5_up")
            if sent > 1: fired.append("news_bullish")
            if sent < -1: fired.append("news_bearish")
            if n_tw > max(3.0, 2*avg):
                fired.append("news_burst")
                if sent > 0: fired.append("burst_bullish")
                elif sent < 0: fired.append("burst_bearish")
            events.append((d, sym, r, fired))
    events.sort()
    for d, sym, r, fired in events:
        if last_day != d:
            for cnt in doss.values(): cnt[0]*=GAMMA; cnt[1]*=GAMMA
            last_day = d
        lo = logit(prior)
        for s in fired:
            u, dn = doss[s]; n = u+dn
            lo += (n/(n+20))*(logit((u+1)/(n+2)) - logit(prior))
        p = 1/(1+math.exp(-lo))
        stream.append((d, sym, p, r))
        lab = 1 if r >= 0.0055 else (0 if r <= -0.005 else None)
        if lab is not None:
            for s in fired: doss[s][0 if lab==1 else 1] += 1
    return stream

def plan(T, mu, c):
    """H-step backward induction over the fitted bucket-MDP -> policy[b][w]."""
    V = [[0.0]*3 for _ in range(NB)]           # V[b][w_index], w in (-1,0,1)
    for _ in range(H):
        NV = [[0.0]*3 for _ in range(NB)]
        for b in range(NB):
            for wi, w in enumerate((-1,0,1)):
                best = -1e9
                for wj, w2 in enumerate((-1,0,1)):
                    ev = sum(T[b][b2]*V[b2][wj] for b2 in range(NB))
                    best = max(best, w2*mu[b] - c*abs(w2-w) + ev)
                NV[b][wi] = best
        V = NV
    pol = [[0]*3 for _ in range(NB)]
    for b in range(NB):
        for wi, w in enumerate((-1,0,1)):
            best, arg = -1e9, 0
            for wj, w2 in enumerate((-1,0,1)):
                ev = sum(T[b][b2]*V[b2][wj] for b2 in range(NB))
                v = w2*mu[b] - c*abs(w2-w) + ev
                if v > best: best, arg = v, w2
            pol[b][wi] = arg
    return pol

def run(cost_bps_list=(0, 5, 10, 20)):
    stream = build_stream()
    print(f"stream: {len(stream):,} (symbol,day) decisions")
    results = {}
    for cbps in cost_bps_list:
        c = cbps / 10000.0
        # fitted stats (walk-forward): drift + transitions per bucket, pooled
        drift = [[0.0, 0.0] for _ in range(NB)]     # [sum_r, n]
        trans = [[1.0]*NB for _ in range(NB)]       # Laplace
        lastb = {}
        pos = {a: defaultdict(int) for a in ("naive","greedy","planner")}
        pnl = {a: defaultdict(float) for a in ("naive","greedy","planner")}
        turn = {a: 0.0 for a in pos}
        pol, month = None, None
        for d, sym, p, r in stream:
            b = bucket(p)
            m = d[:7]
            if m != month:  # monthly re-plan on current fitted model
                mu = [ (s/n if n>5 else 0.0) for s,n in drift ]
                T = [[trans[i][j]/sum(trans[i]) for j in range(NB)] for i in range(NB)]
                pol = plan(T, mu, c)
                month = m
            y = d[:4]
            mu_b = drift[b][0]/drift[b][1] if drift[b][1] > 5 else 0.0
            for a in ("naive","greedy","planner"):
                w = pos[a][sym]
                if a == "naive":
                    w2 = (1 if p > 0.5 else -1) if abs(p-0.5) >= 0.005 else 0
                elif a == "greedy":
                    best, w2 = -1e9, w
                    for cand in (-1,0,1):
                        v = cand*mu_b - c*abs(cand-w)
                        if v > best: best, w2 = v, cand
                else:
                    w2 = pol[b][(-1,0,1).index(w)] if pol else 0
                pnl[a][y] += w2*r - c*abs(w2-w)
                turn[a] += abs(w2-w)
                pos[a][sym] = w2
            # walk-forward updates AFTER acting
            drift[b][0] += r; drift[b][1] += 1
            if sym in lastb: trans[lastb[sym]][b] += 1
            lastb[sym] = b
        years = sorted(pnl["naive"])
        results[cbps] = {a: {"total_bps": round(sum(pnl[a].values())*10000, 0),
                             "yearly_pos": sum(v>0 for v in pnl[a].values()),
                             "n_years": len(years),
                             "turnover": round(turn[a], 0)} for a in pnl}
        r0 = results[cbps]
        print(f"\ncost={cbps}bps: " + " | ".join(
            f"{a}: {r0[a]['total_bps']:+,.0f}bps cum, {r0[a]['yearly_pos']}/{r0[a]['n_years']}yr+, "
            f"turn {r0[a]['turnover']:,.0f}" for a in ("naive","greedy","planner")))
    json.dump(results, open(Path(__file__).parent/"position_results.json","w"), indent=1)

if __name__ == "__main__":
    run()
