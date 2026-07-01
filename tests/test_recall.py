import json
from pathlib import Path

from gemmery.eval import transfer_recall_report

FIXTURE = Path(__file__).resolve().parents[1] / "experiments/transfer_recall/agent_queries.json"


def test_browse_reformulation_beats_oneshot_on_transfer_recall():
    """Escape #1+#2 (offline, hashing): real-Claude reformulations (committed
    fixture) recover transfer gems that one-shot problem-surface lookup misses."""
    aq = json.loads(FIXTURE.read_text())
    rep = transfer_recall_report(agent_queries=aq, top_k=5)
    # browse-via-reformulation should clearly beat one-shot, and the dumb
    # MockPolicy should be the weakest (it's the policy that's the bottleneck).
    assert rep.browse_agent_recall > rep.oneshot_recall
    assert rep.browse_agent_recall >= 0.9
    assert len(rep.recovered_by_agent) > len(rep.lost_by_agent)


def test_recall_report_runs_without_agent_queries():
    rep = transfer_recall_report(top_k=5)
    assert rep.browse_agent_recall is None
    assert 0.0 <= rep.oneshot_recall <= 1.0
    assert rep.n == 24
