"""P3: the packaged production loop (init, inject, ledger, fold)."""
import json
import subprocess
import sys

from gemmery.prod import hooks as H


def _in_project(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMMERY_ROOT", str(tmp_path))
    monkeypatch.delenv("GEMMERY_STORE", raising=False)


def test_init_creates_store_and_wires_hooks(tmp_path, monkeypatch, capsys):
    _in_project(tmp_path, monkeypatch)
    H.init(with_hooks=True)
    assert (tmp_path / ".gemmery-store").exists()
    assert ".gemmery-store/" in (tmp_path / ".gitignore").read_text()
    cfg = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert set(cfg["hooks"]) == {"SessionStart", "SessionEnd", "PostToolUse", "PreCompact"}
    # idempotent: no duplicates on second run
    H.init(with_hooks=True)
    cfg2 = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert cfg == cfg2


def test_init_merges_without_clobbering(tmp_path, monkeypatch):
    _in_project(tmp_path, monkeypatch)
    sf = tmp_path / ".claude" / "settings.json"
    sf.parent.mkdir()
    sf.write_text(json.dumps({"model": "opus", "hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "echo hi"}]}]}}))
    H.init(with_hooks=True)
    cfg = json.loads(sf.read_text())
    assert cfg["model"] == "opus"                        # preserved
    starts = json.dumps(cfg["hooks"]["SessionStart"])
    assert "echo hi" in starts and "gemmery inject" in starts


def test_ledger_fold_inject_roundtrip(tmp_path, monkeypatch, capsys):
    _in_project(tmp_path, monkeypatch)
    from gemmery import Action, Gem, IndexKeys, Kind, KnowledgeBody, Provenance
    st = H.get_store()
    st.capture(Gem(kind=Kind.knowledge, provenance=Provenance("librarian", "s"),
                   body=KnowledgeBody(action=Action("dossier", {"tests": ["tests/u"]}),
                                      reasoning="rule R because E",
                                      belief="rule R"),
                   index_keys=IndexKeys(action_type="dossier", domain=["prod"])),
               path="knowledge/r")
    # ledger a pass and a fail via the hook body
    for out, n in (("3 passed", 1), ("1 failed, 2 passed", 1)):
        monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(
            {"tool_input": {"command": "pytest tests/u -q"},
             "tool_response": {"stdout": out}})))
        H.outcome_hook()
    tagged = H._fold_outcomes(st)
    assert tagged == 2
    notes = st.notes(st.history("knowledge/r")[0])
    assert notes["credit"]["n_events"] == 2
    assert abs(notes["credit"]["total"] - (-0.1)) < 1e-9   # +0.1 - 0.2
    H.inject()
    out = capsys.readouterr().out
    assert "[[knowledge/r]]" in out and "1W/1L" in out and "-0.10" in out


def _mk_dossier(H, path, tests=None):
    from gemmery import Action, Gem, IndexKeys, Kind, KnowledgeBody, Provenance
    st = H.get_store()
    st.capture(Gem(kind=Kind.knowledge, provenance=Provenance("librarian", "s"),
                   body=KnowledgeBody(action=Action("dossier", {"tests": tests or []}),
                                      reasoning=f"rule at {path}", belief=f"rule {path}"),
                   index_keys=IndexKeys(action_type="dossier", domain=["prod"])),
               path=path)
    return st


def test_citations_counted_from_assistant_text_only(tmp_path, monkeypatch):
    _in_project(tmp_path, monkeypatch)
    st = _mk_dossier(H, "knowledge/r1")
    # injected context (user role) cites; assistant cites r1 twice
    assistant = "I applied [[knowledge/r1]] here... and again [[knowledge/r1]]; " \
                "also [[knowledge/nonexistent]] which must be ignored"
    cited = H._capture_citations(st, assistant)
    assert list(cited) == ["knowledge/r1"]
    sha = st.history("knowledge/r1")[0]
    assert H.citation_count(st, sha) == 1          # one event per session
    assert st.notes(sha)["credit"]["total"] == 0.0  # usage marks, never scores


def test_verdicts_credit_and_debit_asymmetrically(tmp_path, monkeypatch):
    _in_project(tmp_path, monkeypatch)
    st = _mk_dossier(H, "knowledge/good")
    _mk_dossier(H, "knowledge/bad")
    cited = {p: st.history(p)[0] for p in ("knowledge/good", "knowledge/bad")}
    ops = {"verdicts": [
        {"path": "knowledge/good", "verdict": "helped", "why": "applied"},
        {"path": "knowledge/bad", "verdict": "misled", "why": "wrong turn"},
        {"path": "knowledge/good", "verdict": "neutral", "why": "ignored"},
        {"path": "knowledge/unknown", "verdict": "helped", "why": "not cited"},
    ]}
    n = H._apply_verdicts(st, ops, cited)
    assert n == 2                                   # neutral + uncited skipped
    good = st.notes(cited["knowledge/good"])
    bad = st.notes(cited["knowledge/bad"])
    assert abs(good["credit"]["total"] - 0.05) < 1e-9
    assert abs(bad["credit"]["total"] + 0.10) < 1e-9   # 2x debit
    assert any(v >= 0.5 for v in good["success"].values())
    assert any(v < 0.5 for v in bad["success"].values())


def test_injection_is_credit_ranked_and_capped(tmp_path, monkeypatch, capsys):
    _in_project(tmp_path, monkeypatch)
    st = _mk_dossier(H, "knowledge/d0")
    for i in range(1, 11):
        _mk_dossier(H, f"knowledge/d{i}")
    st.attach_credit(st.history("knowledge/d7")[0], 0.9)     # the earner
    st.attach_credit(st.history("knowledge/d3")[0], -0.5)    # the debtor
    H.inject()
    out = capsys.readouterr().out
    first = out.index("[[knowledge/d7]]")
    assert first < out.index("[[knowledge/d0]]")             # earner leads
    assert "[[knowledge/d3]]" not in out.split("...and")[0] or \
           out.index("[[knowledge/d3]]") > first             # debtor never first
    assert "more dossiers" in out                            # 11 > TOP_K=8
    assert "cited 0x" in out


def test_librarian_never_recurses(tmp_path, monkeypatch, capsys):
    _in_project(tmp_path, monkeypatch)
    monkeypatch.setenv("GEMMERY_NO_HOOKS", "1")
    _mk_dossier(H, "knowledge/r")
    H.librarian([])          # would fold/log if it ran
    H.inject()
    assert capsys.readouterr().out == ""
    assert not (tmp_path / ".gemmery-store" / "librarian.log").exists()
