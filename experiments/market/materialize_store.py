"""Materialize the signal dossiers into a REAL GitStore: one revisable dossier
per signal at signals/<name>, revised monthly as the backtest walked forward,
with credit notes = the signal's evolving track record. Then the browser."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parents[1]))
from gemmery import Action, Gem, GitStore, IndexKeys, KnowledgeBody, Kind, Provenance, TestSpec
import shutil

R = json.load(open(ROOT / "backtest_results.json"))
if (ROOT / "store").exists(): shutil.rmtree(ROOT / "store")
store = GitStore(ROOT / "store", actor="market-agent")
TS = 1_700_500_000
CLAIMS = {
 "mom1_up": "yesterday's gain predicts continuation up. Falsified if p(up|fired) ~ prior at large n.",
 "mom5_up": "5-day uptrend predicts continuation. Same falsification.",
 "big_drop_reversal": "a >=1.5% drop predicts bounce-back. Same falsification.",
 "tweets_bullish": "bullish tweet language (day d-1) predicts up-move on d.",
 "tweets_bearish": "bearish tweet language predicts down-move.",
 "tweet_burst": "abnormal tweet volume predicts up-move (attention -> buying).",
 "burst_bullish": "volume burst + bullish language: strongest attention signal.",
 "burst_bearish": "volume burst + bearish language predicts down-move.",
}
for s, snaps in R["traj"].items():
    for i, (month, p, n) in enumerate(snaps):
        text = (f"# Signal dossier: {s} (as of {month})\n\nClaim: {CLAIMS[s]}\n\n"
                f"Walk-forward track record (decayed): p(up|fired) = {p:.3f}, "
                f"effective n = {n:.0f}.\nVerdict now: "
                + ("EARNING credit (deviates from prior)." if abs(p-0.507) > 0.02
                   else "NOT earning credit (indistinguishable from prior — shrinkage keeps its vote near zero)."))
        gem = Gem(kind=Kind.knowledge,
                  provenance=Provenance("market-agent", "backtest", timestamp=TS + i),
                  body=KnowledgeBody(action=Action("revise_signal", {"signal": s, "month": month}),
                                     reasoning=text, belief=f"{s} track record",
                                     tests=[TestSpec(f"signal::{s}", "future moves", "p deviates from prior")]),
                  index_keys=IndexKeys(action_type="signal_dossier", domain=[s]))
        if i == 0:
            sha = store.capture(gem, path=f"signals/{s}").sha
        else:
            sha = store.revise(gem, f"signals/{s}").sha
        store.attach_credit(sha, round((p - 0.507) * min(1.0, n/200), 4), test=f"signal::{s}")
print(f"store: {store.count_commits()} gems; signals/{{...}} each with "
      f"{len(next(iter(R['traj'].values())))}-revision history")
print("history(signals/tweets_bullish):", len(store.history("signals/tweets_bullish")), "versions")
