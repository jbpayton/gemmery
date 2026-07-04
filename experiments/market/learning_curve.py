"""Learning over time: month-by-month edge of each arm across the full
walk-forward (every prediction was made before its label was learned, so all
months are legitimately out-of-sample)."""
import json, math, sys
from collections import defaultdict, deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from backtest import build_episodes, logit

def run_full():
    eps = build_episodes()
    prior = 0.507
    doss = defaultdict(lambda: [0.0, 0.0])
    GAMMA = 0.997; last_day = None
    tick_log = defaultdict(deque)
    monthly = defaultdict(lambda: {a: [] for a in ("none","flat","gem")})
    conf_cum = []  # (date, running correct-wrong on confident calls)
    run_cw = 0
    for d, tk, lab, r, fired in eps:
        if last_day != d:
            for c in doss.values(): c[0]*=GAMMA; c[1]*=GAMMA
            last_day = d
        m = d[:7]
        monthly[m]["none"].append((prior, lab))
        q = tick_log[tk]
        monthly[m]["flat"].append(((sum(q)/len(q)) if len(q)>=5 else prior, lab))
        lo = logit(prior)
        for s in fired:
            u, dn = doss[s]; n = u+dn
            lo += (n/(n+20)) * (logit((u+1)/(n+2)) - logit(prior))
        p = 1/(1+math.exp(-lo))
        monthly[m]["gem"].append((p, lab))
        if abs(p-0.5) >= 0.02:
            run_cw += 1 if ((p>=0.5) == (lab==1)) else -1
        conf_cum.append((d, run_cw))
        for s in fired: doss[s][0 if lab==1 else 1] += 1
        q.append(lab)
        if len(q)>20: q.popleft()

    def mcc(preds):
        tp=tn=fp=fn=0
        for p,l in preds:
            if p>=0.5 and l: tp+=1
            elif p>=0.5: fp+=1
            elif l: fn+=1
            else: tn+=1
        den = math.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
        return ((tp*tn-fp*fn)/den) if den else 0.0

    months = sorted(monthly)
    out = {"months": months,
           "mcc": {a: [round(mcc(monthly[m][a]),4) for m in months] for a in ("none","flat","gem")},
           "n": [len(monthly[m]["gem"]) for m in months],
           "conf_cum": conf_cum[::25]}
    json.dump(out, open(Path(__file__).parent/"learning_curve.json","w"), indent=1)
    # rolling 3-month
    def roll3(xs): return [round(sum(xs[max(0,i-2):i+1])/len(xs[max(0,i-2):i+1]),4) for i in range(len(xs))]
    g3, f3 = roll3(out["mcc"]["gem"]), roll3(out["mcc"]["flat"])
    print("month      gem-MCC(3mo)  flat-MCC(3mo)")
    for i, m in enumerate(months):
        print(f"{m}   {g3[i]:+8.3f}     {f3[i]:+8.3f}")
    h = len(months)//2
    print(f"\nmean gem monthly MCC: first half {sum(out['mcc']['gem'][:h])/h:+.4f}  "
          f"second half {sum(out['mcc']['gem'][h:])/(len(months)-h):+.4f}")
run_full()
