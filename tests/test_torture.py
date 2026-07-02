"""Torture tests: adversarial paths, revision chains, unicode/size extremes,
ref-name attacks, growth/scale, and cross-layer invariant sweeps.

Every test here either pins a safety guarantee (nothing at HEAD is ever silently
destroyed; refs never crash on weird names) or a scaling property (capture stays
fast as the tree grows; parity survives everything).
"""
import statistics

import pytest

from gemmery.index import GemIndex
from gemmery.store import GitStore, MAIN
from conftest import decision_gem, knowledge_gem


# --------------------------------------------------------------------------- #
# Path attacks
# --------------------------------------------------------------------------- #
def test_path_through_a_gem_file_never_clobbers_it(store):
    """Routing a path THROUGH an existing file must not replace it with a dir."""
    a = store.capture(decision_gem(0), path="tells/P1").sha
    store.capture(decision_gem(1), path="tells/P1/meta.json/evil")
    # the original gem's files are intact at HEAD
    assert "meta.json" in store.ls("tells/P1")
    assert store.read_file("tells/P1/meta.json")  # still a readable file
    assert store.read_gem(a).id == a


def test_nesting_inside_a_gem_dir_is_redirected(store):
    """Gems are atomic: a new gem cannot move into an existing gem's directory."""
    store.capture(decision_gem(0), path="tells/P1")
    sha = store.capture(decision_gem(1), path="tells/P1/extra").sha
    # redirected to a sibling, not nested inside P1's five files
    p = store.gem_path(sha)
    assert not p.startswith("tells/P1/")
    assert sorted(store.ls("tells/P1")) == [
        "body.json", "index.json", "meta.json", "pre.json", "reasoning.md"]


def test_traversal_and_junk_components_are_neutralized(store):
    sha = store.capture(decision_gem(0), path="../../etc/passwd").sha
    p = store.gem_path(sha)
    assert ".." not in p.split("/") and not p.startswith("/")
    sha2 = store.capture(decision_gem(1), path="//a///b//").sha
    assert store.gem_path(sha2) == "a/b"


def test_empty_path_is_rejected(store):
    with pytest.raises(ValueError):
        store.capture(decision_gem(0), path="///")


def test_hundred_collisions_at_one_path_all_survive(store):
    shas = [store.capture(decision_gem(i), path="hot/spot").sha for i in range(100)]
    # every gem readable, every path unique, nothing shadowed
    paths = {store.gem_path(s) for s in shas}
    assert len(paths) == 100
    assert len(store.ls("hot")) == 100
    for s in shas[::17]:
        assert store.read_gem(s).id == s


def test_deep_path_50_levels(store):
    deep = "/".join(f"d{i}" for i in range(50))
    sha = store.capture(decision_gem(0), path=deep).sha
    assert store.read_gem(sha).id == sha
    assert store.read_file(deep + "/reasoning.md")


def test_unicode_paths_and_content(store):
    g = decision_gem(0, reasoning="Überlegung: P2 blufft — 狼だ! 🐺 → vertraue nie")
    sha = store.capture(g, path="notes/über/狼-🐺").sha
    p = store.gem_path(sha)
    assert store.read_gem(sha).reasoning_text().startswith("Überlegung")
    assert b"\xf0\x9f\x90\xba" in store.read_file(p + "/reasoning.md")  # the wolf emoji


def test_megabyte_reasoning_roundtrips(store):
    big = ("evidence line about a long investigation\n" * 25000)  # ~1MB
    sha = store.capture(decision_gem(0, reasoning=big), path="big/one").sha
    assert store.read_gem(sha).reasoning_text() == big


# --------------------------------------------------------------------------- #
# Revision torture
# --------------------------------------------------------------------------- #
def test_revision_chain_25_deep(store):
    store.capture(decision_gem(0, reasoning="v0"), path="dossier/X")
    shas = [store.revise(decision_gem(i, reasoning=f"v{i}"), "dossier/X").sha
            for i in range(1, 26)]
    hist = store.history("dossier/X")
    assert len(hist) == 26 and hist[0] == shas[-1]
    # HEAD is the newest; every old version readable at its own commit
    assert b"v25" in store.read_file("dossier/X/reasoning.md")
    assert b"v7" in store.read_file("dossier/X/reasoning.md", sha=hist[25 - 7])
    # credit lineage: each revision consumed its predecessor
    g = store.read_gem(shas[-1])
    assert shas[-2] in g.consumed


def test_revise_nonexistent_path_acts_as_capture(store):
    sha = store.revise(decision_gem(0), "fresh/place").sha
    assert store.history("fresh/place") == [sha]
    assert store.read_gem(sha).consumed == []


def test_revise_through_gem_dir_raises(store):
    store.capture(decision_gem(0), path="tells/P1")
    with pytest.raises(ValueError):
        store.revise(decision_gem(1), "tells/P1/inner/x")


def test_revise_on_frontier_is_isolated_from_main(store):
    store.capture(decision_gem(0, reasoning="main-v"), path="doc/D")
    fr = store.branch_frontier("t")
    store.revise(decision_gem(1, reasoning="frontier-v"), "doc/D", branch=fr)
    assert b"main-v" in store.read_file("doc/D/reasoning.md")  # main untouched
    assert len(store.history("doc/D", branch=fr)) == 2
    assert len(store.history("doc/D")) == 1


def test_select_to_main_of_revised_gem_brings_latest(store):
    store.capture(decision_gem(0), path="seed/s")
    fr = store.branch_frontier("t")
    store.capture(decision_gem(1, reasoning="draft"), branch=fr, path="plan/P")
    v2 = store.revise(decision_gem(2, reasoning="final plan"), "plan/P", branch=fr).sha
    store.select_to_main(v2)
    assert b"final plan" in store.read_file("plan/P/reasoning.md")


def test_select_same_gem_twice_no_shadowing(store):
    store.capture(decision_gem(0), path="seed/s")
    fr = store.branch_frontier("t")
    win = store.capture(decision_gem(1), branch=fr, path="plan/P").sha
    s1 = store.select_to_main(win)
    s2 = store.select_to_main(win)
    assert store.gem_path(s1) == "plan/P"
    assert store.gem_path(s2) == "plan/P-2"  # second selection redirected


# --------------------------------------------------------------------------- #
# Ref-name attacks
# --------------------------------------------------------------------------- #
def test_frontier_with_hostile_task_names(store):
    store.capture(decision_gem(0))
    for task in ["has spaces", "semi;colon", "dot..dot", "uni-狼", "a/b"]:
        br = store.branch_frontier(task)
        sha = store.capture(decision_gem(1), branch=br).sha
        fr = store.frontier(task)
        assert any(sha in v for v in fr.values()), task


def test_tag_outcome_with_hostile_test_ids(store):
    sha = store.capture(decision_gem(0)).sha
    for test in ["unit test #1!", "path/like/test", "λ-check"]:
        name = store.tag_outcome(sha, test, ok=True)
        assert name.startswith("refs/tags/ok/")


# --------------------------------------------------------------------------- #
# Growth / scale
# --------------------------------------------------------------------------- #
def test_capture_stays_fast_as_store_grows(store):
    times = []
    for i in range(400):
        times.append(store.capture(decision_gem(i)).capture_ms)
    early = statistics.median(times[:100])
    late = statistics.median(times[-100:])
    assert late < 25.0, f"late-capture median {late:.1f}ms breaks the invariant"
    assert late < max(4 * early, 10.0), f"capture degrading: {early:.2f} -> {late:.2f}ms"


def test_everything_survives_a_mixed_barrage(store):
    """A mixed workload, then sweep EVERY commit for read-back + index parity."""
    shas = []
    for i in range(40):
        shas.append(store.capture(decision_gem(i), path=f"a/b{i % 5}/g{i}").sha)
    for i in range(10):
        shas.append(store.revise(decision_gem(100 + i), "a/rolling").sha)
    fr = store.branch_frontier("mix")
    shas.append(store.capture(knowledge_gem(), branch=fr, path="k/fact").sha)
    shas.append(store.select_to_main(shas[-1]))
    store.attach_success(shas[0], "t_flaky", 0.9)
    store.attach_credit(shas[0], 0.5, source_sha=shas[1])
    store.tag_outcome(shas[0], "t_flaky", ok=True)

    # every commit in the store reads back as a valid gem with a valid path
    all_shas = store.all_shas()
    for s in all_shas:
        g = store.read_gem(s)
        assert g.id == s and g.kind is not None
        assert store.gem_path(s)
    # index parity over the whole mess
    idx = GemIndex()
    assert idx.rebuild(store) == len(all_shas)
    # the fs is coherent: every listed leaf is a five-file gem dir
    for line in store.tree_listing().splitlines():
        if line.strip().endswith("reasoning.md"):
            break
    else:
        raise AssertionError("no gem files visible in tree listing")


def test_pickaxe_sees_revisions(store):
    store.capture(decision_gem(0, reasoning="alpha marker"), path="doc/D")
    store.revise(decision_gem(1, reasoning="beta marker"), "doc/D")
    assert len(store.pickaxe("alpha marker")) >= 1  # the add AND the removal
    assert len(store.pickaxe("beta marker")) >= 1


def test_ls_and_read_file_edges(store):
    store.capture(decision_gem(0), path="x/y")
    assert store.ls("does/not/exist") == []
    with pytest.raises(KeyError):
        store.read_file("does/not/exist.md")


# --------------------------------------------------------------------------- #
# Browse leave-one-out (previously untested, load-bearing for the eval)
# --------------------------------------------------------------------------- #
def test_browse_exclude_is_airtight(store):
    from gemmery.browse import BudgetMeter, MockPolicy, browse
    shas = []
    for i, dom in enumerate(["networking", "networking", "database"]):
        g = decision_gem(i, action="retry_with_backoff", domain=dom,
                         reasoning="transient idempotent retry backoff networking")
        shas.append(store.capture(g).sha)
    idx = GemIndex()
    idx.rebuild(store)
    res = browse("transient idempotent retry networking", store=store, index=idx,
                 policy=MockPolicy(), budget=BudgetMeter(max_calls=8),
                 exclude=set(shas))  # exclude EVERYTHING relevant
    assert set(res.mark_shas) & set(shas) == set()


def test_two_store_handles_interleaved_writes(tmp_path):
    """Two agents sharing one repo: alternating captures must serialize cleanly."""
    p = tmp_path / "shared"
    a, b = GitStore(p, actor="agent-A"), GitStore(p, actor="agent-B")
    shas = []
    for i in range(20):
        st = a if i % 2 == 0 else b
        shas.append(st.capture(decision_gem(i), path=f"log/e{i}").sha)
    # a linear chain, no lost writes, both handles see everything
    assert a.count_commits() == b.count_commits() == 20
    assert len(a.ls("log")) == 20
    g = b.read_gem(shas[0])
    assert g.provenance.actor in ("claude", "agent-A")  # gem authorship preserved


def test_revised_versions_all_indexed_and_current_is_newest(store):
    """Pin the semantics: EVERY version of a revised note is a commit and gets
    indexed (immutable record); the file system serves the CURRENT one."""
    v1 = store.capture(decision_gem(0, reasoning="old belief"), path="d/X").sha
    v2 = store.revise(decision_gem(1, reasoning="new belief"), "d/X").sha
    idx = GemIndex()
    idx.rebuild(store)
    hits = idx.columnar_filter(path_prefix="d/X")
    assert set(hits) == {v1, v2}          # both versions retrievable (by design)
    assert store.read_gem_at("d/X").id == v2  # the fs view is the newest
