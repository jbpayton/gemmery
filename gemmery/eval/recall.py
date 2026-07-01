"""Transfer-recall experiment (escape #1 + #2, spec §0).

Does *browsing* surface a cross-surface, same-method ("transfer") gem better than
a single one-shot lookup?  This isolates the retrieval question GitOfThoughts
controlled away by holding the agent fixed — and it does **not** need hard solve
tasks, so it is measurable cheaply and honestly.

Leave-one-out over the dataset: for each query task, the gold set is the
same-schema / different-surface gems (the method-transfer cell). We compare:

* ``one_shot``      — a single problem-surface top-k lookup.
* ``browse_mock``   — the deterministic MockPolicy browse (marks).
* ``browse_agent``  — retrieval driven by *real* reformulations (e.g. produced by
  Claude sub-agents), passed in as ``agent_queries`` — the AnthropicPolicy
  reformulate step, executed out of band so the experiment is reproducible from a
  committed fixture without re-running models.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..browse import BudgetMeter, MockPolicy, browse, one_shot
from ..index import GemIndex
from ..store import GitStore
from .dataset import build_dataset
from .harness import populate_memory


@dataclass
class RecallReport:
    n: int
    top_k: int
    embedder: str
    oneshot_recall: float
    browse_mock_recall: float
    browse_agent_recall: Optional[float]
    recovered_by_agent: list[str] = field(default_factory=list)  # one-shot missed, agent found
    lost_by_agent: list[str] = field(default_factory=list)       # one-shot found, agent missed
    oneshot_misses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def transfer_recall_report(embedder=None, agent_queries: Optional[dict] = None,
                           top_k: int = 5, tasks=None) -> RecallReport:
    tasks = tasks if tasks is not None else build_dataset()
    tmp = tempfile.mkdtemp(prefix="gemmery-recall-")
    store = GitStore(Path(tmp) / "mem")
    sha_by = populate_memory(store, tasks)
    idx = GemIndex(embedder=embedder) if embedder is not None else GemIndex()
    idx.rebuild(store)
    meta = {sha_by[t.id]: (t.schema_id, t.surface_domain) for t in tasks}
    all_shas = set(idx.columnar_filter())

    o_hit = bm_hit = ba_hit = 0
    recovered, lost, misses = [], [], []
    have_agent = agent_queries is not None

    for t in tasks:
        excl = {sha_by[t.id]}
        gold = {s for s, (sc, su) in meta.items()
                if sc == t.schema_id and su != t.surface_domain}
        restrict = all_shas - excl

        o = one_shot(t.problem_text, store=store, index=idx, exclude=excl, top_k=top_k)
        o_ok = any(m.sha in gold for m in o.marks)
        o_hit += o_ok
        if not o_ok:
            misses.append(t.id)

        b = browse(t.problem_text, store=store, index=idx, policy=MockPolicy(),
                   budget=BudgetMeter(max_calls=8), exclude=excl,
                   top_k=top_k, max_iters=4)
        bm_hit += any(s in gold for s in b.mark_shas)

        if have_agent:
            qs = agent_queries.get(t.id) or [t.problem_text]
            hits = idx.hybrid_retrieve(qs, field="reasoning", top_k=top_k,
                                       restrict=restrict)
            a_ok = any(h.sha in gold for h in hits)
            ba_hit += a_ok
            if a_ok and not o_ok:
                recovered.append(t.id)
            if o_ok and not a_ok:
                lost.append(t.id)

    n = len(tasks)
    return RecallReport(
        n=n, top_k=top_k,
        embedder=(embedder.name if embedder is not None else GemIndex().embedder.name),
        oneshot_recall=o_hit / n,
        browse_mock_recall=bm_hit / n,
        browse_agent_recall=(ba_hit / n) if have_agent else None,
        recovered_by_agent=recovered, lost_by_agent=lost, oneshot_misses=misses,
    )
