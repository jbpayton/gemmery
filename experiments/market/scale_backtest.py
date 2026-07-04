"""FNSPID scale-up: 85 NASDAQ stocks, 2010-2023, walk-forward, per-era scoring.

Same arms and signal family as the StockNet run; the questions at scale:
(1) does the credit-dossier edge REPLICATE across eras (the kill-switch's
replication treatment, on real regimes)? (2) drift discipline across 14 years;
(3) the beyond-context fact: this news corpus is ~280M tokens = ~1,400x a 200K
context window — no read-based memory can hold it; the dossiers are exact
aggregates over all of it.
"""
from __future__ import annotations
import csv, json, math
from collections import defaultdict, deque
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "fnspid"

def load_news():
    news = {}
    with open(D / "news_daily.csv") as f:
        for r in csv.DictReader(f):
            news[(r["Stock_symbol"], r["day"])] = (int(r["n"]), int(r["sent"]))
    return news

def load_price(sym):
    rows = []
    try:
        with open(D / "prices" / f"{sym}.csv") as f:
            for r in csv.DictReader(f):
                try: rows.append((r["date"], float(r["adj close"])))
                except (ValueError, KeyError): continue
    except FileNotFoundError:
        return []
    rows.sort()
    return [(d, c) for d, c in rows if "2009-06-01" <= d <= "2023-12-31"]

def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p/(1-p))

def run():
    news = load_news()
    syms = sorted(set(s for s, _ in news.keys()))
    eps = []
    for sym in syms:
        pr = load_price(sym)
        ratios = [(d1, c1/c0 - 1) for (d0,c0),(d1,c1) in zip(pr, pr[1:])]
        trail = deque(maxlen=20)
        for i in range(1, len(ratios)):
            d, r = ratios[i]
            d_prev = ratios[i-1][0]
            n_tw, sent = news.get((sym, d_prev), (0, 0))
            avg = (sum(trail)/len(trail)) if trail else 0.0
            trail.append(n_tw)
            lab = 1 if r >= 0.0055 else (0 if r <= -0.005 else None)
            if lab is None or d < "2010-01-01":
                continue
            r1, r5 = ratios[i-1][1], sum(x[1] for x in ratios[max(0,i-5):i])/min(5,i)
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
            eps.append((d, sym, lab, fired))
    eps.sort()
    print(f"{len(eps):,} labeled episodes, {len(syms)} symbols, "
          f"{eps[0][0]} -> {eps[-1][0]}")

    prior = sum(e[2] for e in eps)/len(eps)
    doss = {v: defaultdict(lambda: [0.0,0.0]) for v in ("all","decay")}
    GAMMA, last_day = 0.997, None
    tlog = defaultdict(deque)
    yearly = defaultdict(lambda: {a: [] for a in ("none","flat","gem_all","gem_decay")})
    conf_cum, run_cw = [], 0
    for d, sym, lab, fired in eps:
        if last_day != d:
            for c in doss["decay"].values(): c[0]*=GAMMA; c[1]*=GAMMA
            last_day = d
        y = d[:4]
        yearly[y]["none"].append((prior, lab))
        q = tlog[sym]
        yearly[y]["flat"].append(((sum(q)/len(q)) if len(q)>=5 else prior, lab))
        for v, name in (("all","gem_all"),("decay","gem_decay")):
            lo = logit(prior)
            for s in fired:
                u, dn = doss[v][s]; n = u+dn
                lo += (n/(n+20))*(logit((u+1)/(n+2)) - logit(prior))
            p = 1/(1+math.exp(-lo))
            yearly[y][name].append((p, lab))
            if name == "gem_decay" and abs(p-0.5) >= 0.02:
                run_cw += 1 if ((p>=0.5)==(lab==1)) else -1
        conf_cum.append((d, run_cw))
        for v in ("all","decay"):
            for s in fired: doss[v][s][0 if lab==1 else 1] += 1
        q.append(lab)
        if len(q)>20: q.popleft()

    def mcc(preds, tau=0.0):
        tp=tn=fp=fn=0
        for p,l in preds:
            if abs(p-0.5) < tau: continue
            if p>=0.5 and l: tp+=1
            elif p>=0.5: fp+=1
            elif l: fn+=1
            else: tn+=1
        den = math.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
        cov = (tp+tn+fp+fn)/max(1,len(preds))
        return (((tp*tn-fp*fn)/den) if den else 0.0), cov

    years = sorted(yearly)
    out = {"years": years, "n": {y: len(yearly[y]["none"]) for y in years}}
    print(f"\n{'year':>5} {'n':>7} {'flat':>8} {'gem_all':>8} {'gem_decay':>9} {'gem@tau.02 (cov)':>18}")
    for a in ("none","flat","gem_all","gem_decay"):
        out[a] = {}
    out["gem_sel"] = {}
    pos_years = 0
    for y in years:
        row = []
        for a in ("none","flat","gem_all","gem_decay"):
            m,_ = mcc(yearly[y][a]); out[a][y] = round(m,4); row.append(m)
        msel, cov = mcc(yearly[y]["gem_decay"], tau=0.02)
        out["gem_sel"][y] = (round(msel,4), round(cov,3))
        pos_years += out["gem_decay"][y] > 0
        print(f"{y:>5} {out['n'][y]:>7} {row[1]:+8.3f} {row[2]:+8.3f} {row[3]:+9.3f} "
              f"{msel:+9.3f} ({cov:4.1%})")
    print(f"\ngem_decay positive in {pos_years}/{len(years)} years "
          f"(sign test p≈{0.5**len(years)*sum(math.comb(len(years),k) for k in range(pos_years,len(years)+1)):.4f})")
    out["conf_cum"] = conf_cum[::400]
    json.dump(out, open(Path(__file__).parent/"scale_results.json","w"), indent=1)

if __name__ == "__main__":
    run()
