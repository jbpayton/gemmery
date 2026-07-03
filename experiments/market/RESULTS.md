# Market memory backtest — StockNet, 3 arms, walk-forward

Real data, mechanical (contamination-free) arms, standard test split
(2015-10-01..2016-01-01, n=3,720), memory accumulating from 2014-01-01.
Signals fire strictly from information before the predicted move (prices
through d-1, tweets posted on d-1).

## Headline (test split)

| arm | acc | MCC | Brier |
|---|---|---|---|
| none (train prior) | 0.513 | +0.000 | 0.2499 |
| flat log (recency read of raw episodes) | 0.504 | −0.001 | 0.2636 |
| dossiers, all-history | 0.508 | +0.032 | 0.2497 |
| **dossiers, decayed (revision discipline)** | 0.509 | **+0.036** | **0.2497** |

- **The pre-registered band was honest:** the credit-dossier arm lands at
  +0.036 MCC — inside/just above the "meaningful" +0.01–0.03 range, far below
  anything suspicious. (Reference: the StockNet paper's neural model = 0.081
  full-coverage MCC.)
- **Flat memory is useless-to-harmful on real markets** (−0.001 MCC, worst
  Brier): reading raw recent episodes carries no signal — the same flat-file
  null as everywhere, now on real data.
- **Decay beats all-history** (+0.036 vs +0.032): the drift lesson (revise,
  don't hoard) replicates weakly but in the right direction.
- Note accuracy is a misleading metric here (always-up exploits class imbalance
  at 0.513 with ZERO discrimination) — exactly why MCC was pre-registered.

## Knowing when you know (abstention)

Selective prediction where the dossiers are confident:
τ=0.02 → 30% coverage, acc 0.540, **MCC +0.100**; the 1.2% most-confident calls
hit 65% accuracy. A memory that knows when it knows nothing concentrates its
edge — this is the calibration value the plain accuracy number hides.

## What earned credit (and what didn't) — fully interpretable

| signal dossier | p(up\|fired) | n_eff | verdict |
|---|---|---|---|
| burst_bullish (volume burst + bullish tweets) | **0.559** | 358 | earning |
| tweet_burst (abnormal tweet volume) | **0.554** | 573 | earning |
| tweets_bullish | **0.549** | 507 | earning |
| mom1_up / mom5_up / big_drop_reversal | 0.490–0.492 | ~6,800 | **dead** — market ate them; shrinkage keeps their vote ≈0 |
| tweets_bearish | 0.531 (predicting UP!) | 45 | broken lexicon or contrarian; too little n — correctly near-ignored |

The credit system did on real markets what it did at the long table: **found
the live signal (attention + sentiment in tweets), spent nothing on the dead
ones (price momentum — huge n, zero deviation), and stayed humble where n was
tiny.** The full dossier evolution is materialized in a real store —
`signals/<name>` with 24 monthly revisions each and credit notes
(`browser.html` to drill it).

## Honest scope
One dataset, one test window (Q4-2015), lexicon sentiment, mechanical arms
only. No trading-cost simulation, no absolute-alpha claim. The LLM comparative
arms (memory-delta at matched contamination) and the FNSPID scale-up
(beyond-context news history) are the designed next steps.
