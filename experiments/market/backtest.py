"""3-arm walk-forward backtest on StockNet: none vs flat-log vs credit dossiers.

All arms are MECHANICAL (contamination-free; these carry the headline numbers).
Chronological sweep 2014-01-01 -> 2016-01-01; memory accumulates from day one;
only the standard test window (2015-10-01..2016-01-01) is scored.

Arms:
  none    — train prior (always-up, p = prior).
  flat    — raw recency log: majority of the ticker's last 20 labeled episodes.
  gemmery — credit-weighted SIGNAL DOSSIERS: per-signal walk-forward track
            records (fired->up / fired->down), shrunk by sample size, combined
            in log-odds space. Two variants: all-history counts vs
            exponentially-decayed counts (the drift lesson: revise, don't hoard).

Signals fire from information available strictly before the predicted move:
prices through d-1 and tweets posted on d-1.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from loader import (DATA, TRAIN_END, VAL_END, TEST_END, START,  # noqa: E402
                    load_prices, tickers, tweets_on)

BULL = ("beat", "beats", "upgrade", "upgraded", "buy", "bullish", "rally",
        "surge", "record", "strong", "growth", "outperform", "up")
BEAR = ("miss", "misses", "downgrade", "downgraded", "sell", "bearish", "crash",
        "plunge", "weak", "lawsuit", "recall", "underperform", "down", "cut")


def lex_sent(texts):
    s = 0
    for t in texts:
        tl = t.lower()
        s += sum(w in tl for w in BULL) - sum(w in tl for w in BEAR)
    return s


def build_episodes():
    """Chronological stream: (date, ticker, label, ratio, fired-signals)."""
    eps = []
    for tk in tickers():
        prices = load_prices(tk)
        ratios = [(d1, c1 / c0 - 1) for (d0, c0, _), (d1, c1, _) in zip(prices, prices[1:])]
        counts = deque(maxlen=20)
        for i in range(1, len(ratios)):
            d, r = ratios[i]
            if not (START < d <= TEST_END):
                # still update trailing tweet stats pre-window
                pass
            lab = 1 if r >= 0.0055 else (0 if r <= -0.005 else None)
            d_prev = ratios[i - 1][0]
            tw = tweets_on(tk, d_prev)
            n_tw = len(tw)
            avg = (sum(counts) / len(counts)) if counts else 0.0
            counts.append(n_tw)
            if lab is None or not (START < d <= TEST_END):
                continue
            sent = lex_sent(tw) if tw else 0
            r1 = ratios[i - 1][1]
            r5 = sum(x[1] for x in ratios[max(0, i - 5):i]) / min(5, i)
            fired = []
            if r1 > 0:
                fired.append("mom1_up")
            if r1 <= -0.015:
                fired.append("big_drop_reversal")
            if r5 > 0:
                fired.append("mom5_up")
            if sent > 2:
                fired.append("tweets_bullish")
            if sent < -2:
                fired.append("tweets_bearish")
            if n_tw > max(4.0, 2 * avg):
                fired.append("tweet_burst")
                if sent > 0:
                    fired.append("burst_bullish")
                elif sent < 0:
                    fired.append("burst_bearish")
            eps.append((d, tk, lab, r, fired))
    eps.sort()
    return eps


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def run():
    eps = build_episodes()
    prior = 0.507  # train up-rate (measured in loader)

    # dossiers: signal -> [up, down]; two variants
    doss = {v: defaultdict(lambda: [0.0, 0.0]) for v in ("all", "decay")}
    GAMMA = 0.997                       # ~230-day half-life
    last_day = {"decay": None}
    tick_log = defaultdict(deque)       # flat arm: recent labels per ticker

    results = {a: [] for a in ("none", "flat", "gem_all", "gem_decay")}
    signal_traj = defaultdict(list)     # monthly credit snapshots
    cur_month = None

    for d, tk, lab, r, fired in eps:
        in_test = d > VAL_END
        # ---- decay step (once per new day) ----
        if last_day["decay"] != d:
            for c in doss["decay"].values():
                c[0] *= GAMMA
                c[1] *= GAMMA
            last_day["decay"] = d

        # ---- predictions (before seeing the label) ----
        if in_test:
            results["none"].append((prior, lab))
            q = tick_log[tk]
            p_flat = (sum(q) / len(q)) if len(q) >= 5 else prior
            results["flat"].append((p_flat, lab))
            for v, name in (("all", "gem_all"), ("decay", "gem_decay")):
                lo = logit(prior)
                for s in fired:
                    u, dn = doss[v][s]
                    n = u + dn
                    p_s = (u + 1) / (n + 2)
                    k = n / (n + 20)            # shrink young signals
                    lo += k * (logit(p_s) - logit(prior))
                results[name].append((1 / (1 + math.exp(-lo)), lab))

        # ---- learn (walk-forward update AFTER predicting) ----
        for v in ("all", "decay"):
            for s in fired:
                doss[v][s][lab == 0] += 0 or 0  # no-op guard
                doss[v][s][0 if lab == 1 else 1] += 1
        q = tick_log[tk]
        q.append(lab)
        if len(q) > 20:
            q.popleft()

        # monthly signal snapshot (decay variant)
        m = d[:7]
        if m != cur_month:
            cur_month = m
            for s, (u, dn) in doss["decay"].items():
                n = u + dn
                if n > 0:
                    signal_traj[s].append((m, (u + 1) / (n + 2), n))

    # ---- scoring ----
    def mcc_acc_brier(preds, thresh=0.5):
        tp = tn = fp = fn = 0
        brier = 0.0
        for p, lab in preds:
            brier += (p - lab) ** 2
            pred = 1 if p >= thresh else 0
            if pred and lab: tp += 1
            elif pred and not lab: fp += 1
            elif not pred and lab: fn += 1
            else: tn += 1
        n = len(preds)
        den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        mcc = ((tp * tn - fp * fn) / den) if den else 0.0
        return (tp + tn) / n, mcc, brier / n, n

    out = {}
    print(f"{'arm':10s} {'acc':>6s} {'mcc':>7s} {'brier':>7s}   (test n)")
    for a in ("none", "flat", "gem_all", "gem_decay"):
        acc, mcc, br, n = mcc_acc_brier(results[a])
        out[a] = {"acc": round(acc, 4), "mcc": round(mcc, 4), "brier": round(br, 4)}
        print(f"{a:10s} {acc:6.3f} {mcc:+7.3f} {br:7.4f}   ({n})")

    # abstention curve for gem_decay
    print("\nabstention (gem_decay): predict only when |p-0.5| >= tau")
    curve = []
    for tau in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10):
        sel = [(p, l) for p, l in results["gem_decay"] if abs(p - 0.5) >= tau]
        if len(sel) < 30:
            break
        acc, mcc, br, n = mcc_acc_brier(sel)
        cov = n / len(results["gem_decay"])
        curve.append((tau, cov, acc, mcc))
        print(f"  tau={tau:.2f}  coverage={cov:5.1%}  acc={acc:.3f}  mcc={mcc:+.3f}")

    json.dump({"arms": out, "abstention": curve,
               "signals": {s: v[-1] for s, v in signal_traj.items()},
               "traj": {s: v for s, v in signal_traj.items()}},
              open(Path(__file__).parent / "backtest_results.json", "w"), indent=1)
    print("\nfinal signal dossiers (decayed): p(up|fired), effective n")
    for s, v in sorted(signal_traj.items()):
        m, p, n = v[-1]
        print(f"  {s:18s} p={p:.3f}  n_eff={n:6.1f}")


if __name__ == "__main__":
    run()
