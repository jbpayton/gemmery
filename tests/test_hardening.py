"""P2 hardening: multi-writer safety (flock) and the secrets boundary.

The concurrency tests use real separate PROCESSES, each with its own GitStore
handle on one repo — the exact shape of two Claude sessions sharing a store.
"""
import json
import multiprocessing as mp

from gemmery import GitStore
from gemmery.store import MAIN
from conftest import decision_gem


def _writer(store_path, worker, n, q):
    st = GitStore(store_path)
    shas = []
    for i in range(n):
        shas.append(st.capture(decision_gem(i, reasoning=f"w{worker}-{i}"),
                               path=f"work/w{worker}/g{i}").sha)
    q.put(shas)


def test_concurrent_writers_lose_nothing(tmp_path):
    store_path = str(tmp_path / "store")
    GitStore(store_path)  # init
    q = mp.Queue()
    procs = [mp.Process(target=_writer, args=(store_path, w, 25, q))
             for w in range(4)]
    [p.start() for p in procs]
    [p.join(60) for p in procs]
    all_shas = [s for _ in range(4) for s in q.get()]
    assert len(all_shas) == 100

    st = GitStore(store_path)
    # every gem is on main's history: the ref never lost a commit to a race
    on_main = set(st._git_lines(["log", "--format=%H", MAIN]))
    assert set(all_shas) <= on_main and len(on_main) == 100
    # the chain is linear (each commit has exactly one parent except the root)
    for sha in all_shas:
        g = st.read_gem(sha)
        assert g.id == sha
    # whole memory tree contains all 100 paths
    assert sum(len(st.ls(f"work/w{w}")) for w in range(4)) == 100


def _noter(store_path, sha, n, worker):
    st = GitStore(store_path)
    for i in range(n):
        st.attach_credit(sha, 0.01, test=f"w{worker}-{i}")


def test_concurrent_note_appends_lose_nothing(tmp_path):
    """Without the lock this loses events: notes are read-modify-write."""
    store_path = str(tmp_path / "store")
    st = GitStore(store_path)
    sha = st.capture(decision_gem(0), path="hot/gem").sha
    procs = [mp.Process(target=_noter, args=(store_path, sha, 25, w))
             for w in range(4)]
    [p.start() for p in procs]
    [p.join(60) for p in procs]
    credit = GitStore(store_path).notes(sha)["credit"]
    assert credit["n_events"] == 100
    assert abs(credit["total"] - 1.0) < 1e-9


def test_secrets_are_redacted_at_capture(store):
    leaky = ("deploy decision: use key AKIAIOSFODNN7EXAMPLE and token "
             "ghp_abcdefghijklmnopqrstuvwxyz0123456789 for the push; "
             "header was Authorization: Bearer c2VjcmV0LXRva2VuLWhlcmU=")
    r = store.capture(decision_gem(0, reasoning=leaky), path="dec/leak")
    assert "aws-access-key" in r.redactions
    assert "github-token" in r.redactions
    text = store.read_gem(r.sha).reasoning_text()
    assert "AKIAIOSFODNN7EXAMPLE" not in text
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in text
    assert "[REDACTED:aws-access-key]" in text
    # nothing in ANY stored blob leaks the key
    raw = store.read_file("dec/leak/reasoning.md")
    assert b"AKIA" not in raw


def test_private_key_block_never_lands(store):
    pem = ("context:\n-----BEGIN RSA PRIVATE KEY-----\n"
           "MIIEpAIBAAKCAQEA7cv0Zzzz\nmore\n-----END RSA PRIVATE KEY-----\ndone")
    r = store.capture(decision_gem(0, reasoning=pem), path="dec/pem")
    assert "private-key-block" in r.redactions
    assert b"BEGIN RSA PRIVATE KEY" not in store.read_file("dec/pem/reasoning.md")


def test_clean_content_untouched(store):
    clean = "P2 voted against P4 on day 3; the sk- prefix alone is fine, as is AKI."
    r = store.capture(decision_gem(0, reasoning=clean), path="dec/clean")
    assert r.redactions == ()
    assert store.read_gem(r.sha).reasoning_text() == clean


def test_redaction_can_be_disabled(tmp_path):
    st = GitStore(tmp_path / "raw", redact_secrets=False)
    r = st.capture(decision_gem(0, reasoning="AKIAIOSFODNN7EXAMPLE"), path="d/x")
    assert r.redactions == ()
    assert "AKIAIOSFODNN7EXAMPLE" in st.read_gem(r.sha).reasoning_text()


def test_pathlog_matches_git_log(store):
    """history() via pathlog must equal git log exactly, incl. revisions,
    collisions, and selections."""
    from gemmery.store import MAIN
    a = store.capture(decision_gem(0, reasoning="v0"), path="doc/D").sha
    b = store.revise(decision_gem(1, reasoning="v1"), "doc/D").sha
    store.capture(decision_gem(2), path="doc/D")          # collision -> doc/D-2
    fr = store.branch_frontier("t")
    w = store.capture(decision_gem(3), branch=fr, path="plan/P").sha
    store.select_to_main(w)
    for p in ("doc/D", "doc/D-2", "plan/P"):
        fast = store.history(p)
        slow = store._git_lines(["log", "--format=%H", MAIN, "--", p])
        assert fast == slow, p
    assert store.history("doc/D") == [b, a]


def test_pathlog_rebuild_roundtrip(store):
    for i in range(10):
        store.capture(decision_gem(i), path=f"a/g{i}")
        if i % 3 == 0:
            store.revise(decision_gem(i, reasoning=f"r{i}"), "a/hot")
    before = {p: store.history(p) for p in ["a/hot"] + [f"a/g{i}" for i in range(10)]}
    n = store.rebuild_pathlog()
    assert n >= 14
    after = {p: store.history(p) for p in before}
    assert before == after


def test_pathlog_migration_on_old_store(tmp_path, store):
    """A store whose pathlog is deleted (old-format) migrates on open."""
    import pathlib
    store.capture(decision_gem(0), path="m/x")
    store.revise(decision_gem(1), "m/x")
    plog = pathlib.Path(store.repo.path) / "gemmery-pathlog.jsonl"
    expect = store.history("m/x")
    plog.unlink()
    from gemmery import GitStore
    st2 = GitStore(store.path)
    assert plog.exists()
    assert st2.history("m/x") == expect
