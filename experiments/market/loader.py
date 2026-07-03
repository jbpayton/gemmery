"""StockNet loader — walk-forward-safe access to prices, labels, and tweets.

Follows the StockNet paper's conventions so results are comparable:
  * movement ratio r_t = adj_close_t / adj_close_{t-1} - 1
  * label: DOWN if r <= -0.5%, UP if r >= 0.55%, else discarded (noise band)
  * standard split: train 2014-01-01..2015-07-31, val ..2015-09-30,
    test 2015-10-01..2016-01-01

Everything is exposed chronologically; nothing here reads the future.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "stocknet"
TRAIN_END, VAL_END, TEST_END = "2015-07-31", "2015-09-30", "2016-01-01"
START = "2014-01-01"


def load_prices(ticker):
    rows = []
    with open(DATA / "price" / "raw" / f"{ticker}.csv") as f:
        for r in csv.DictReader(f):
            try:
                rows.append((r["Date"], float(r["Adj Close"]), float(r["Volume"])))
            except ValueError:
                continue
    rows.sort()
    return rows


def movement_series(ticker):
    """[(date, ratio, label)] with label in {1 up, 0 down, None discarded}."""
    prices = load_prices(ticker)
    out = []
    for (d0, c0, _), (d1, c1, _) in zip(prices, prices[1:]):
        r = c1 / c0 - 1
        lab = 1 if r >= 0.0055 else (0 if r <= -0.005 else None)
        out.append((d1, r, lab))
    return out


def tweets_on(ticker, date):
    p = DATA / "tweet" / "raw" / ticker / date
    if not p.exists():
        return []
    out = []
    with open(p) as f:
        for line in f:
            try:
                t = json.loads(line)
                out.append(t.get("text", ""))
            except json.JSONDecodeError:
                continue
    return out


def tickers():
    return sorted(p.stem for p in (DATA / "price" / "raw").glob("*.csv"))


def episodes(split="test"):
    """Chronological (ticker, date, ratio, label, n_tweets) for a split."""
    lo, hi = {"train": (START, TRAIN_END), "val": (TRAIN_END, VAL_END),
              "test": (VAL_END, TEST_END)}[split]
    out = []
    for tk in tickers():
        for d, r, lab in movement_series(tk):
            if lo < d <= hi and lab is not None:
                out.append((tk, d, r, lab))
    out.sort(key=lambda x: (x[1], x[0]))
    return out


if __name__ == "__main__":
    for sp in ("train", "val", "test"):
        eps = episodes(sp)
        up = sum(e[3] for e in eps)
        print(f"{sp:5s}: {len(eps):6d} episodes  up-rate {up/len(eps):.3f}")
    tk = "AAPL"
    tw = tweets_on(tk, "2015-10-05")
    print(f"sample: {tk} 2015-10-05 has {len(tw)} tweets; first: {tw[0][:70] if tw else '-'}")
