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


def test_tree_accumulates_like_a_filesystem(store):
    """Each commit's tree is the WHOLE memory state (spec §2.1: post = tree)."""
    s1 = store.capture(decision_gem(0), path="tells/P1").sha
    s2 = store.capture(decision_gem(1), path="tells/P2").sha
    s3 = store.capture(decision_gem(2), path="decisions/round1").sha
    # at HEAD the filesystem holds everything
    assert store.ls() == ["decisions/", "tells/"]
    assert store.ls("tells") == ["P1/", "P2/"]
    assert "reasoning.md" in store.ls("tells/P1")
    # at the first commit only the first gem exists
    assert store.ls(sha=s1) == ["tells/"]
    assert store.ls("tells", sha=s1) == ["P1/"]
    # the effect of s3 is exactly its own addition (diff parent -> self)
    d = store.diff(s2, s3)
    assert "decisions/round1" in d and "tells/P1" not in d


def test_read_gem_finds_own_gem_in_accumulated_tree(store):
    a = store.capture(decision_gem(0, action="alpha"), path="k/a").sha
    b = store.capture(decision_gem(1, action="beta"), path="k/b").sha
    assert store.read_gem(a).action().name == "alpha"
    assert store.read_gem(b).action().name == "beta"


def test_capture_never_shadows_existing_path(store):
    a = store.capture(decision_gem(0), path="tells/P1").sha
    b = store.capture(decision_gem(1), path="tells/P1").sha  # same path
    # both gems remain readable and both live in the final filesystem
    assert store.read_gem(a).id == a and store.read_gem(b).id == b
    assert store.ls("tells") == ["P1-2/", "P1/"]


def test_select_to_main_brings_only_the_gem_subtree(store):
    store.capture(decision_gem(0), path="base/seed")
    fr = store.branch_frontier("t")
    store.capture(decision_gem(1, action="noise"), branch=fr, path="scratch/noise")
    win = store.capture(decision_gem(2, action="winner"), branch=fr,
                        path="plans/win").sha
    sel = store.select_to_main(win)
    # main gains the winner but NOT the frontier's other content
    assert "plans/" in store.ls()
    assert "scratch/" not in store.ls()
    assert store.read_gem(sel).action().name == "winner"


def test_read_file_at_commit(store):
    s1 = store.capture(decision_gem(0, reasoning="first thoughts"), path="n/one").sha
    store.capture(decision_gem(1, reasoning="later thoughts"), path="n/two")
    assert b"first thoughts" in store.read_file("n/one/reasoning.md")
    # and the state AS OF s1 lacks n/two entirely
    assert store.ls("n", sha=s1) == ["one/"]


def test_revise_keeps_stable_path_and_history(store):
    v1 = store.capture(decision_gem(0, reasoning="v1: P2 seems shifty"),
                       path="knowledge/tells/P2").sha
    v2 = store.revise(decision_gem(1, reasoning="v2: P2 fakes Seer when wolf"),
                      "knowledge/tells/P2").sha
    # HEAD holds the revision at the SAME path (no P2-2)
    assert store.ls("knowledge/tells") == ["P2/"]
    assert b"v2:" in store.read_file("knowledge/tells/P2/reasoning.md")
    # full version history preserved, newest first
    assert store.history("knowledge/tells/P2") == [v2, v1]
    # current view helper returns the latest version
    assert store.read_gem_at("knowledge/tells/P2").id == v2
    # the revision consumed its predecessor (credit lineage follows)
    assert v1 in store.read_gem(v2).consumed
    # and the old version is still readable at its own commit
    assert b"v1:" in store.read_file("knowledge/tells/P2/reasoning.md", sha=v1)


def test_default_path_is_sharded_by_day(store):
    sha = store.capture(decision_gem(0)).sha
    p = store.gem_path(sha)
    parts = p.split("/")
    assert parts[0] == "decision" and len(parts) == 3  # kind/date/name
    assert len(parts[1].split("-")) == 3  # YYYY-MM-DD
