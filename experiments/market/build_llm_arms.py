"""LLM comparative arms: same features both arms; memory arm adds dossier
track records (as-of prediction day, walk-forward-correct). No tickers, dates,
or raw headlines anywhere -> contamination neutralized, delta isolates memory."""
import json, math, random, sys
from collections import defaultdict, deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from scale_backtest import load_news, load_price, logit

def main():
    news = load_news()
    syms = sorted(set(s for s, _ in news.keys()))
    prior = 0.507
    doss = defaultdict(lambda: [0.0, 0.0])
    GAMMA, last_day = 0.997, None
    rng = random.Random(42)
    events = []
    for sym in syms:
        pr = load_price(sym)
        ratios = [(d1, c1/c0-1) for (d0,c0),(d1,c1) in zip(pr, pr[1:])]
        trail = deque(maxlen=20)
        for i in range(1, len(ratios)):
            d, r = ratios[i]
            n_tw, sent = news.get((sym, ratios[i-1][0]), (0, 0))
            avg = (sum(trail)/len(trail)) if trail else 0.0
            trail.append(n_tw)
            if d < "2010-01-01": continue
            events.append((d, sym, r, ratios[i-1][1],
                           sum(x[1] for x in ratios[max(0,i-5):i])/min(5,i),
                           n_tw, avg, sent))
    events.sort()
    sample = []
    for d, sym, r, r1, r5, n_tw, avg, sent in events:
        if last_day != d:
            for c in doss.values(): c[0]*=GAMMA; c[1]*=GAMMA
            last_day = d
        fired = []
        if r1 > 0: fired.append("mom1_up")
        if r1 <= -0.015: fired.append("big_drop_reversal")
        if r5 > 0: fired.append("mom5_up")
        if sent > 1: fired.append("news_bullish")
        if sent < -1: fired.append("news_bearish")
        burst = n_tw > max(3.0, 2*avg)
        if burst:
            fired.append("news_burst")
            if sent > 0: fired.append("burst_bullish")
            elif sent < 0: fired.append("burst_bearish")
        lo = logit(prior)
        dstats = {}
        for s in fired:
            u, dn = doss[s]; n = u+dn
            lo += (n/(n+20))*(logit((u+1)/(n+2)) - logit(prior))
            dstats[s] = (round((u+1)/(n+2), 3), round(n))
        p = 1/(1+math.exp(-lo))
        lab = 1 if r >= 0.0055 else (0 if r <= -0.005 else None)
        # sample confident-dossier, news-involved episodes from 2016 onward
        if (lab is not None and d >= "2016-01-01" and abs(p-0.5) >= 0.02
                and any(s.startswith(("news", "burst")) for s in fired)
                and rng.random() < 0.02 and len(sample) < 60):
            sample.append(dict(r1=round(r1*100,2), r5=round(r5*100,2),
                               n_articles=n_tw, burst_ratio=round(n_tw/max(avg,.5),1),
                               sentiment=sent, fired=fired, dstats=dstats,
                               p_mech=round(p,3), label=lab))
        if lab is not None:
            for s in fired: doss[s][0 if lab==1 else 1] += 1
    truth = {f"E{i}": e["label"] for i, e in enumerate(sample)}
    json.dump(truth, open(Path(__file__).parent/"llm_truth.json","w"), indent=1)
    json.dump([{k: e[k] for k in ("p_mech","label")} for e in sample],
              open(Path(__file__).parent/"llm_mech.json","w"), indent=1)

    RULE = ("You are a quantitative analyst. For EACH anonymized stock-day below "
            "(no tickers, no dates), predict whether the next trading day's move "
            "is UP (>=+0.55%) or DOWN (<=-0.5%). Return ONLY JSON mapping episode "
            'id to "U" or "D", e.g. {"E0":"U"}.\n\n')
    cold, mem = RULE, RULE
    for i, e in enumerate(sample):
        blk = (f"=== EPISODE E{i} ===\n"
               f"yesterday's move: {e['r1']:+.2f}%; 5-day mean move: {e['r5']:+.2f}%\n"
               f"news yesterday: {e['n_articles']} articles ({e['burst_ratio']}x "
               f"normal volume); net sentiment score {e['sentiment']:+d}\n")
        cold += blk + "\n"
        mem += blk + "MEMORY (walk-forward track records of the patterns active today):\n"
        for s, (ps, n) in e["dstats"].items():
            mem += (f"  - {s}: across {n} past occurrences, next-day was UP "
                    f"{ps:.1%} of the time\n")
        mem += "\n"
    (Path(__file__).parent/"prompt_llm_cold.txt").write_text(cold)
    (Path(__file__).parent/"prompt_llm_mem.txt").write_text(mem)
    print(f"{len(sample)} episodes; up-rate {sum(truth.values())/len(truth):.2f}; "
          f"prompts KB: cold {len(cold)//1024}, mem {len(mem)//1024}")

main()
