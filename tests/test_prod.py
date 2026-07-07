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
    assert set(cfg["hooks"]) == {"SessionStart", "SessionEnd", "PostToolUse"}
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
