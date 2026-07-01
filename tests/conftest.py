import tempfile

import pytest

from gemmery import (
    Action,
    Cost,
    DecisionBody,
    Gem,
    IndexKeys,
    Kind,
    KnowledgeBody,
    ObservationBody,
    Provenance,
    Reversibility,
    TestSpec,
)
from gemmery.store import GitStore


@pytest.fixture
def store(tmp_path):
    return GitStore(tmp_path / "store")


def decision_gem(i=0, action="retry_with_backoff", domain="networking",
                 pre=None, reasoning=None, tests=None, consumed=None):
    return Gem(
        kind=Kind.decision,
        provenance=Provenance(actor="claude", session_id="s1"),
        body=DecisionBody(
            action=Action(action, {"base_ms": 100}),
            reasoning=reasoning or f"Chose {action} for transient errors (instance {i}).",
            tests=tests if tests is not None else [TestSpec("t_flaky", "pytest -k flaky", "exit 0")],
            pre=pre or {"error_class": "transient", "idempotent": True},
        ),
        cost=Cost(tokens=120, tool_calls=1),
        reversibility_class=Reversibility.reversible,
        index_keys=IndexKeys(
            precondition_shape=list((pre or {}).keys()) or ["transient", "idempotent"],
            action_type=action,
            domain=[domain],
            test_ids=["t_flaky"],
        ),
        consumed=consumed or [],
    )


def knowledge_gem(belief="retries help transient failures", credence=0.7):
    return Gem(
        kind=Kind.knowledge,
        provenance=Provenance(actor="claude", session_id="s1"),
        body=KnowledgeBody(
            action=Action("believe", {}),
            reasoning="Observed across many incidents.",
            belief=belief,
            credence=credence,
            tests=[TestSpec("justify_src", "check source", "cited")],
        ),
        index_keys=IndexKeys(action_type="belief", domain=["reliability"]),
    )


def observation_gem(content="HTTP 503 from upstream"):
    return Gem(
        kind=Kind.observation,
        provenance=Provenance(actor="claude", session_id="s1"),
        body=ObservationBody(content=content),
        index_keys=IndexKeys(action_type="observe"),
    )
