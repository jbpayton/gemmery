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

---

## Scale-up: FNSPID NASDAQ-100 (85 stocks, 2010–2023, 184,767 episodes)

The replication treatment our own protocol demanded — same signal family, same
arms, walked forward through **six market regimes**. News corpus: 358K articles
≈ **280M tokens ≈ 1,400× a 200K context window** (the beyond-context regime,
quantified on real data: no read-based memory can hold this; the dossiers are
exact aggregates over all of it).

| | result |
|---|---|
| credit dossiers (decayed), yearly MCC | **positive 13/14 years** (only 2022 bear −0.008); sign test **p ≈ 0.0009** |
| selective (τ=0.02) | positive **14/14 years** (+0.002…+0.085) |
| flat recency log | negative in 10/14 years — the flat-null replicates too |

Honest observations: the edge attenuates 2020–2022 (news volume tripled and
the naive lexicon's signal thinned — a real drift the dossiers survived but
didn't escape), recovering in 2023. The StockNet +0.036 was not a one-window
fluke; it is a small, real, replicating edge — exactly the size the
efficient-market prior said a legitimate one would be.

---

## Position game: simulation finally gets a job on real data

Sequential consequences via transaction costs: position w ∈ {−1,0,+1} per
(symbol, day), reward w·r − c·|Δw|, 263,848 decisions, 2010–2023. All arms share
the SAME dossier beliefs; only the planning horizon differs. World model =
two more walk-forward exact-aggregate dossiers (drift per belief-bucket + the
bucket transition matrix); the planner runs H=10 backward induction over that
fitted MDP, re-planned monthly.

| cost | naive (chase) | greedy (1-step) | planner (simulate) |
|---|---|---|---|
| 0 bps | +2,217 | +2,435 | +2,251 |
| 5 bps | +1,905 | +2,289 | +2,112 |
| 10 bps | +1,594 | +2,359 | +2,203 |
| **20 bps** | +971 | +1,066 | **+2,291** |

(cumulative %-points summed over 85 single-symbol books; turnover: naive fixed
at 62.3K, greedy 19.9K→1.1K, planner 15.9K→1.1K)

- **The planner's edge is cost-invariant** (+2,251→+2,291 across the sweep): it
  plans its own turnover down as friction rises — the no-trade band emerges
  from lookahead, not hand-tuning.
- **At 20 bps, simulation more than doubles the myopic arms**: greedy's 1-step
  horizon can't justify holding positions whose multi-day cumulative edge
  exceeds the round-trip cost; the planner holds through noise.
- **At low friction, simulation adds nothing (slightly negative vs greedy)** —
  the session's horizon-threshold law translated to markets: lookahead pays
  exactly when actions have consequences; when switching is free, myopia is fine.

Honest scope: comparative claim only (same beliefs, different horizons);
cumulative bps ≠ portfolio Sharpe (no capital constraints/slippage curve);
mechanical arms, contamination-free.
