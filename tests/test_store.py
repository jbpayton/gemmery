import statistics

import pytest

from gemmery.store import GitStore, MAIN
from conftest import decision_gem, knowledge_gem, observation_gem


def test_capture_under_25ms_invariant(store):
    times = [store.capture(decision_gem(i)).capture_ms for i in range(30)]
    # Invariant 9: capture must be cheap. Assert on the median to avoid a
    # cold-cache first-commit outlier flaking CI.
    assert statistics.median(times) < 25.0, f"median capture {statistics.median(times):.1f}ms"


def test_capture_roundtrip_and_parent_chain(store):
    s0 = store.capture(decision_gem(0)).sha
    s1 = store.capture(decision_gem(1)).sha
    g1 = store.read_gem(s1)
    assert g1.parents[0] == s0
    assert g1.action().name == "retry_with_backoff"


def test_initial_success_note_is_pending(store):
    sha = store.capture(decision_gem()).sha
    assert store.notes(sha)["success"] == {"t_flaky": "pending"}


def test_attach_success_and_credit_are_append_only(store):
    sha = store.capture(decision_gem()).sha
    store.attach_success(sha, "t_flaky", 0.8, source="x")
    store.attach_success(sha, "t_flaky", 0.6, source="y")  # re-judge
    store.attach_credit(sha, 0.5, source_sha="x")
    store.attach_credit(sha, -0.1, source_sha="y")
    n = store.notes(sha)
    assert n["success"]["t_flaky"] == 0.6  # last judgement wins
    assert abs(n["credit"]["total"] - 0.4) < 1e-9  # signed sum


def test_tag_outcome_and_by_tag(store):
    sha = store.capture(decision_gem()).sha
    store.tag_outcome(sha, "t_flaky", ok=True)
    store.tag_outcome(sha, "t_flaky", ok=False)
    assert any("ok/t_flaky/" in t for t in store.by_tag("ok/*"))
    assert any("fail/t_flaky/" in t for t in store.by_tag("fail/*"))


def test_grep_and_pickaxe(store):
    store.capture(decision_gem(0, action="retry_with_backoff"))
    store.capture(decision_gem(1, action="circuit_breaker"))
    assert len(store.grep("retry_with_backoff")) >= 1
    # -G matches the diff text (more useful for content recall than -S)
    assert len(store.pickaxe("circuit_breaker", regex=True)) >= 1


def test_late_dependency_edge_sidecar(store):
    a = store.capture(decision_gem(0)).sha
    b = store.capture(decision_gem(1)).sha
    store.add_dependency_edge(b, a, role="consumed")
    assert a in store.read_gem(b).consumed


def test_frontier_branch_and_select_to_main(store):
    store.capture(decision_gem(0))  # seed main
    fr = store.branch_frontier("taskA")
    r = store.capture(decision_gem(1, action="speculative"), branch=fr)
    frontier_gems = store.frontier("taskA")
    assert frontier_gems[fr] == [r.sha]
    sel = store.select_to_main(r.sha)
    # selected gem now reachable from main; original frontier gem untouched
    main_log = store._git_lines(["log", "--format=%H", MAIN])
    assert sel in main_log
    assert store.read_gem(r.sha).id == r.sha  # frontier gem still readable


def test_checkout_returns_gem_and_ancestry(store):
    shas = [store.capture(decision_gem(i)).sha for i in range(4)]
    gem, ancestry = store.checkout(shas[-1])
    assert gem.id == shas[-1]
    assert len(ancestry) == 4  # full chain to root


def test_observation_and_knowledge_capture(store):
    so = store.capture(observation_gem()).sha
    sk = store.capture(knowledge_gem()).sha
    assert store.read_gem(so).kind.value == "observation"
    assert store.read_gem(sk).kind.value == "knowledge"
    # knowledge has a justification test -> pending note
    assert store.notes(sk)["success"] == {"justify_src": "pending"}
