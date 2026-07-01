import numpy as np

from gemmery.index import GemIndex, HashingEmbedder
from conftest import decision_gem, knowledge_gem


def _populate(store):
    shas = []
    specs = [
        ("retry_with_backoff", "networking", {"transient": 1, "idempotent": 1}),
        ("circuit_breaker", "networking", {"transient": 1, "cascading": 1}),
        ("add_db_index", "database", {"slow_query": 1, "large_table": 1}),
        ("memoize", "compute", {"pure_fn": 1, "hot_path": 1}),
        ("retry_with_backoff", "messaging", {"transient": 1, "idempotent": 1}),
    ]
    for i, (action, domain, pre) in enumerate(specs):
        g = decision_gem(i, action=action, domain=domain, pre=pre,
                         reasoning=f"Applied {action} because {list(pre)} held.")
        shas.append(store.capture(g).sha)
    return shas


def test_rebuild_parity(store):
    _populate(store)
    store.capture(knowledge_gem())
    idx = GemIndex(embedder=HashingEmbedder())
    n = idx.rebuild(store)
    assert n == store.count_commits() == idx.count()  # parity assertion holds


def test_columnar_filters(store):
    shas = _populate(store)
    idx = GemIndex()
    idx.rebuild(store)
    # by action
    res = idx.columnar_filter(action_type="retry_with_backoff")
    assert set(res) == {shas[0], shas[4]}
    # by domain
    assert set(idx.columnar_filter(domain="database")) == {shas[2]}
    # by precondition token (the solution-shape handle)
    assert set(idx.columnar_filter(pre_any=["transient"])) == {shas[0], shas[1], shas[4]}
    assert set(idx.columnar_filter(pre_all=["transient", "idempotent"])) == {shas[0], shas[4]}


def test_credit_and_outcome_filters(store):
    shas = _populate(store)
    store.attach_credit(shas[0], 0.9)
    store.tag_outcome(shas[0], "t_flaky", ok=True)
    idx = GemIndex()
    idx.rebuild(store)
    assert shas[0] in idx.columnar_filter(min_credit=0.5)
    assert idx.columnar_filter(outcome="ok") == [shas[0]]


def test_hybrid_retrieve_prefilters_then_ranks(store):
    shas = _populate(store)
    idx = GemIndex()
    idx.rebuild(store)
    # structured pre-filter to retry gems, then semantic rank
    hits = idx.hybrid_retrieve(
        "transient network failure handling",
        filters={"action_type": "retry_with_backoff"},
        field="reasoning", top_k=5,
    )
    assert {h.sha for h in hits} <= {shas[0], shas[4]}
    assert all(h.field == "reasoning" for h in hits)


def test_hybrid_never_cold_without_filters(store):
    shas = _populate(store)
    memoize_sha = shas[3]
    idx = GemIndex()
    idx.rebuild(store)
    # No structured filter -> must still lexically narrow before semantic.
    hits = idx.hybrid_retrieve("memoize a pure hot path function", top_k=3)
    assert hits  # found something
    # the memoize gem should be recognized among the top hits
    assert memoize_sha in {h.sha for h in hits}


def test_rebuild_is_idempotent_and_from_git_only(store):
    _populate(store)
    idx = GemIndex()
    idx.rebuild(store)
    first = sorted(idx.columnar_filter())
    idx.rebuild(store)  # rebuild again from git alone
    assert sorted(idx.columnar_filter()) == first
