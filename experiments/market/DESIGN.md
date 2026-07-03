# Market memory testbed — StockNet backtest (design + protocol)

## Why this dataset
[StockNet](https://github.com/yumoxu/stocknet-dataset): 88 US stocks, daily
prices + per-day stock tweets, 2014–2016, with a standard split and published
baselines (paper acc≈0.582 / MCC≈0.081; later models ≈0.60–0.62; chance≈0.51).
Small (68MB), canonical, comparable. Scale-up path: FNSPID (15.7M news articles,
1999–2023 — its 23GB news file is literally the beyond-context-window regime).
Contamination-free alternatives (StockBench, PriceSeer) use 2025+ windows but
aren't fully downloadable offline here.

## What this tests that our synthetic games couldn't
A real drifting world with REAL headroom scarcity: markets are near-efficient,
so absolute accuracy claims are capped tightly. Verified mechanically:
always-up 0.513, 1d-momentum 0.509, 5d-momentum 0.460 (test split, walk-forward).

## Mapping onto the machinery (the Long Table on real data)
- **Episode = gem**: pre = {recent price features, day's tweets}, action =
  predicted movement (or abstain), post = realized next-day move, test = the
  realization -> signed success. Walk-forward chronological; nothing reads the future.
- **Signal dossiers** at stable paths (e.g. `signals/tweet-burst`, `signals/
  momentum-reversal`, per-ticker `tells/<TICKER>`): claims with falsification
  conditions, REVISED as regimes drift; credit = realized track record
  ("fired 40 times, vindicated 24") — earned, signed, per-signal.
- **Arms** (same 3-arm discipline): none / flat (raw episode log, read-what-fits)
  / gemmery (credit-weighted current dossiers + exact aggregates). Mechanical
  fitters first (contamination-free); LLM arms comparative-only.

## Leakage & contamination protocol (non-negotiable)
1. Walk-forward only; labels use the paper's noise band (±0.5%/0.55%).
2. 2014–16 is inside LLM pretraining: NO absolute LLM-accuracy claims. LLM arms
   measure DELTAS (memory vs no-memory, same base model = matched contamination).
3. Mechanical arms (count/credit-based) are contamination-free and carry the
   headline numbers.

## Metrics & the honest null
Accuracy + MCC (comparability), Brier/calibration (memory should improve
*calibration* even if accuracy is capped), per-signal credit curves, and
abstention-quality (a memory that knows when it knows nothing has value the
accuracy metric hides). Pre-registered expectation: the efficient-market null
(memory adds ~nothing to accuracy) is LIVE — deltas of +0.01–0.03 MCC would be
meaningful; anything bigger is suspect and gets the replication treatment.
