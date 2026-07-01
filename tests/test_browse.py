from gemmery.browse import (
    BudgetMeter,
    MockPolicy,
    Permeability,
    browse,
    one_shot,
)
from gemmery.index import GemIndex
from conftest import decision_gem


def _populated(store):
    specs = [
        ("retry_with_backoff", "networking", {"transient": 1, "idempotent": 1}),
        ("circuit_breaker", "networking", {"transient": 1, "cascading": 1}),
        ("add_db_index", "database", {"slow_query": 1, "large_table": 1}),
        ("memoize", "compute", {"pure_fn": 1, "hot_path": 1}),
    ]
    shas = []
    for i, (a, d, pre) in enumerate(specs):
        g = decision_gem(i, action=a, domain=d, pre=pre,
                         reasoning=f"Used {a} because {' '.join(pre)} held in a {d} task.")
        shas.append(store.capture(g).sha)
    idx = GemIndex()
    idx.rebuild(store)
    return idx, shas


def test_browse_recognizes_relevant_gem(store):
    idx, shas = _populated(store)
    res = browse(
        "transient idempotent retry networking failure",
        store=store, index=idx, policy=MockPolicy(),
        budget=BudgetMeter(max_calls=8),
    )
    assert shas[0] in res.mark_shas  # the retry gem is recognized


def test_budget_is_a_hard_ceiling(store):
    idx, _ = _populated(store)
    # 5 calls -> at most 2 full iterations (2 calls each); never exceed ceiling
    meter = BudgetMeter(max_calls=5)
    res = browse("slow database query large table", store=store, index=idx,
                 budget=meter, max_iters=99)
    assert res.budget["calls"] <= 5
    assert res.iterations <= 2


def test_empty_store_control_is_a_true_control(store, tmp_path):
    """browse + empty memory: same loop, same budget, zero marks (spec §10.1 arm 3)."""
    idx, _ = _populated(store)
    from gemmery.store import GitStore
    empty_store = GitStore(tmp_path / "empty")
    empty_idx = GemIndex()
    empty_idx.rebuild(empty_store)  # parity over zero commits

    budget = BudgetMeter(max_calls=8)
    res = browse("transient idempotent retry", store=empty_store, index=empty_idx,
                 budget=budget, max_iters=4)
    assert res.mark_shas == []  # nothing to recognize
    assert res.budget["calls"] > 0  # but compute WAS spent (the control's point)


def test_permeability_membrane_seals_sibling_frontiers(store):
    # main has one accepted gem; a sibling frontier has a relevant abandoned gem.
    idx, shas = _populated(store)
    fr = store.branch_frontier("taskX")
    g = decision_gem(99, action="exotic_retry", domain="networking",
                     pre={"transient": 1, "idempotent": 1},
                     reasoning="Abandoned exotic transient idempotent retry idea.")
    fr_sha = store.capture(g, branch=fr).sha
    idx.rebuild(store)

    sealed = browse("transient idempotent retry", store=store, index=idx,
                    permeability=Permeability.sealed, budget=BudgetMeter(max_calls=8))
    assert fr_sha not in set(sealed.mark_shas)  # sibling frontier not cross-read

    opened = browse("transient idempotent retry exotic abandoned idea",
                    store=store, index=idx, permeability=Permeability.open,
                    budget=BudgetMeter(max_calls=8))
    assert fr_sha in set(opened.mark_shas)  # synthesis can reach it


def test_one_shot_makes_no_model_calls(store):
    idx, shas = _populated(store)
    res = one_shot("memoize pure hot path", store=store, index=idx, top_k=3)
    assert res.mode == "one_shot"
    assert res.budget["calls"] == 0
    assert res.marks  # still retrieves
