"""Mechanical sanity baselines on the standard StockNet test split (walk-forward)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import math
from loader import episodes, movement_series, tickers, TRAIN_END

def mcc(tp, tn, fp, fn):
    d = math.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
    return ((tp*tn - fp*fn) / d) if d else 0.0

def score(pred):  # pred: (ticker,date)->0/1
    eps = episodes("test")
    tp=tn=fp=fn=0
    for tk,d,r,lab in eps:
        p = pred.get((tk,d))
        if p is None: continue
        if p==1 and lab==1: tp+=1
        elif p==0 and lab==0: tn+=1
        elif p==1 and lab==0: fp+=1
        else: fn+=1
    n = tp+tn+fp+fn
    return (tp+tn)/n, mcc(tp,tn,fp,fn), n

# 1) always up
pred_up = {(tk,d):1 for tk,d,r,l in episodes("test")}
# 2) 1-day momentum & 3) 5-day mean momentum & 4) contrarian
pred_m1, pred_m5, pred_c1 = {}, {}, {}
for tk in tickers():
    ser = movement_series(tk)
    for i,(d,r,lab) in enumerate(ser):
        if i>=1: pred_m1[(tk,d)] = 1 if ser[i-1][1]>0 else 0
        if i>=5:
            m = sum(x[1] for x in ser[i-5:i])/5
            pred_m5[(tk,d)] = 1 if m>0 else 0
        if i>=1: pred_c1[(tk,d)] = 0 if ser[i-1][1]>0 else 1
for name,p in [("always-up",pred_up),("momentum-1d",pred_m1),
               ("momentum-5d",pred_m5),("contrarian-1d",pred_c1)]:
    a,m,n = score(p)
    print(f"{name:14s} acc={a:.3f}  mcc={m:+.3f}  (n={n})")
print("\npublished reference points (same split): StockNet paper acc≈0.582 mcc≈0.081;")
print("strong later models acc≈0.60-0.62. Market is near-efficient: headroom is thin by design.")
