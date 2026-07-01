import pytest

from gemmery import Gem, Kind, PENDING
from gemmery.model import (
    DecisionBody,
    KnowledgeBody,
    ObservationBody,
    clamp_score,
)
from gemmery.valuation import (
    append_line,
    fold_credit,
    fold_success,
    success_pending_event,
    success_score_event,
    credit_event,
)
from conftest import decision_gem, knowledge_gem, observation_gem


def test_body_kind_mismatch_rejected():
    g = decision_gem()
    with pytest.raises(TypeError):
        Gem(kind=Kind.observation, provenance=g.provenance, body=g.body)


def test_files_roundtrip_excludes_success():
    g = decision_gem()
    files = g.to_files()
    assert set(files) == {
        "gem/meta.json", "gem/body.json", "gem/reasoning.md",
        "gem/pre.json", "gem/index.json",
    }
    # success must never be serialized into the commit (Invariant 1)
    for data in files.values():
        assert b"success" not in data.lower() or b"successor" in data.lower()
    g2 = Gem.from_files(files, sha="deadbeef", parents=["cafe"])
    assert g2.kind is Kind.decision
    assert g2.action().name == g.action().name
    assert g2.pre() == g.pre()
    assert g2.reasoning_text() == g.reasoning_text()


def test_each_kind_roundtrips():
    for g in (decision_gem(), knowledge_gem(), observation_gem()):
        g2 = Gem.from_files(g.to_files())
        assert g2.kind is g.kind
        assert type(g2.body) is type(g.body)


def test_pending_is_three_valued():
    # PENDING must not be confusable with a score and must refuse truthiness
    with pytest.raises(TypeError):
        bool(PENDING)
    assert PENDING is not 0.0  # noqa: F632 - intentional identity check


def test_clamp_score_bounds():
    assert clamp_score(5) == 1.0
    assert clamp_score(-5) == -1.0
    assert clamp_score(0.3) == 0.3


def test_success_fold_pending_then_scored():
    text = None
    text = append_line(text, success_pending_event("t1", 1.0))
    text = append_line(text, success_pending_event("t2", 1.0))
    cells = fold_success(text)
    assert cells["t1"].is_pending and cells["t2"].is_pending
    # score t1 twice -> track record n_scored == 2, last wins
    text = append_line(text, success_score_event("t1", 0.2, 2.0))
    text = append_line(text, success_score_event("t1", 0.9, 3.0))
    cells = fold_success(text)
    assert cells["t1"].value == 0.9 and cells["t1"].n_scored == 2
    assert cells["t2"].is_pending  # untouched test stays ⊥, not 0.0


def test_credit_fold_signed_sum():
    text = None
    text = append_line(text, credit_event(0.5, 1.0, source="a"))
    text = append_line(text, credit_event(-0.2, 2.0, source="b"))
    text = append_line(text, credit_event(0.1, 3.0, source="a"))
    s = fold_credit(text)
    assert abs(s.total - 0.4) < 1e-9
    assert abs(s.by_source["a"] - 0.6) < 1e-9
    assert s.n_events == 3
