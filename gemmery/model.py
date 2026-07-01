"""The gem: the one captured record type (spec §2).

A gem is simultaneously a Hoare triple ``{pre} action {post}``, a STRIPS/PDDL
operator instance (preconditions + effects), and an RL transition
``(s, a, r, s')``.  That convergence is intentional: one record type serves
episodic memory, a planning-operator library, and procedural skills at once.

Design notes that are load-bearing (do not "simplify" away):

* The body is a **sum type** keyed on ``kind`` — decision / observation /
  knowledge — not one nullable row (spec §2.1).  Flattening decays the schema
  to a lowest common denominator and kills the searchability that motivates it.
* ``success`` is **not** part of the gem's committed bytes.  It is mutable
  valuation and lives in a git note (Invariant 1, spec §2.2).  The dataclasses
  here therefore never serialize ``success`` into the on-disk files.
* On disk a gem is five files under ``gem/`` (spec §2.2).  The (de)serialization
  lives here so ``store`` and ``index`` share exactly one representation.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Enumerations (closed vocabularies — spec §2.1)
# --------------------------------------------------------------------------- #
class Kind(str, Enum):
    decision = "decision"
    observation = "observation"
    knowledge = "knowledge"


class Reversibility(str, Enum):
    """Spec §8 — governs whether a git rewind also rewinds the world."""

    pure = "pure"  # deliberation; freely rewindable
    reversible = "reversible"  # a revert action exists
    compensable = "compensable"  # carries its own inverse (saga log)
    irreversible = "irreversible"  # history and world diverge on rewind


# Three-valued success (Invariant 3).  ``pending`` (⊥) is *never judged*; it is
# distinct from a score of 0.0 ("present, inert") and from any negative score
# ("present, harmful").  We represent ⊥ as a dedicated sentinel so it can never
# be confused with a float.
class _Pending:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "PENDING"

    def __bool__(self) -> bool:  # ⊥ is not falsy-as-failure; guard misuse
        raise TypeError(
            "PENDING is three-valued; test `is PENDING` explicitly rather than "
            "relying on truthiness (collapsing ⊥ poisons credit — Invariant 3)."
        )


PENDING = _Pending()

# A success score is a signed float in [-1, +1] or PENDING.
Score = float  # documented range [-1.0, +1.0]


def clamp_score(s: float) -> float:
    """Success/credit scores are signed and bounded (Invariant 2)."""
    return max(-1.0, min(1.0, float(s)))


# --------------------------------------------------------------------------- #
# Envelope (every gem) — spec §2.1
# --------------------------------------------------------------------------- #
@dataclass
class Provenance:
    actor: str  # agent id / model id
    session_id: str
    timestamp: float = field(default_factory=time.time)
    signed: bool = False  # whether the commit was `-S` signed


@dataclass
class Cost:
    """What producing this gem spent (spec §2.1; consumed by credit later)."""

    tokens: int = 0
    wall_time_s: float = 0.0
    tool_calls: int = 0


@dataclass
class IndexKeys:
    """Extracted handles for browsing (spec §6) — written to ``index.json``.

    Note this is indexed on *solution/method shape* (precondition tokens,
    action type), not only problem surface — the GitOfThoughts escape (§5).
    """

    precondition_shape: list[str] = field(default_factory=list)
    action_type: str = ""
    domain: list[str] = field(default_factory=list)
    test_ids: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Typed bodies — spec §2.1
# --------------------------------------------------------------------------- #
@dataclass
class Action:
    """Typed action descriptor: name + bound arguments (near-PDDL, §8.3)."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSpec:
    """A bound verifier.  Success is meaningless unbound (Invariant 2)."""

    id: str
    how_to_run: str = ""  # command / description of how to evaluate
    what_counts: str = ""  # what a pass means; the success criterion


@dataclass
class DecisionBody:
    action: Action
    reasoning: str  # the *why*; the extrapolation field (§7.4) -> reasoning.md
    tests: list[TestSpec] = field(default_factory=list)
    # ``pre`` predicate is extracted to pre.json; the canonical pre/post is the
    # parent-tree -> self-tree diff, carried by git, not duplicated here.
    pre: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeBody:
    """A fact is a decision whose action is belief revision (spec §2.1)."""

    action: Action  # the epistemic update
    reasoning: str  # justification narrative
    belief: str = ""  # post: "believe X"
    credence: float = 0.5  # storage-time credence; graded later by track record
    tests: list[TestSpec] = field(default_factory=list)  # justification / source check
    pre: dict[str, Any] = field(default_factory=dict)  # "did not hold belief X"


@dataclass
class ObservationBody:
    """Raw sensor/tool output incited by a decision (spec §2.1)."""

    content: str
    reasoning: str = ""  # optional note on relevance
    pre: dict[str, Any] = field(default_factory=dict)


Body = DecisionBody | KnowledgeBody | ObservationBody


# --------------------------------------------------------------------------- #
# The gem
# --------------------------------------------------------------------------- #
@dataclass
class Gem:
    """One captured unit.  ``id``/``parents`` are filled by git on capture."""

    kind: Kind
    provenance: Provenance
    body: Body
    cost: Cost = field(default_factory=Cost)
    reversibility_class: Reversibility = Reversibility.pure
    index_keys: IndexKeys = field(default_factory=IndexKeys)
    consumed: list[str] = field(default_factory=list)  # dep-graph out-edges (§2.1)
    incited_by: Optional[str] = None  # dep-graph in-edge cause
    # Filled by the store after commit:
    id: Optional[str] = None
    parents: list[str] = field(default_factory=list)

    # ----- consistency helpers ------------------------------------------- #
    def __post_init__(self) -> None:
        self.kind = Kind(self.kind)
        self.reversibility_class = Reversibility(self.reversibility_class)
        self._check_body_kind()

    def _check_body_kind(self) -> None:
        expected = {
            Kind.decision: DecisionBody,
            Kind.knowledge: KnowledgeBody,
            Kind.observation: ObservationBody,
        }[self.kind]
        if not isinstance(self.body, expected):
            raise TypeError(
                f"kind={self.kind.value} requires {expected.__name__}, "
                f"got {type(self.body).__name__}"
            )

    def reasoning_text(self) -> str:
        return getattr(self.body, "reasoning", "") or ""

    def tests(self) -> list[TestSpec]:
        return list(getattr(self.body, "tests", []) or [])

    def action(self) -> Optional[Action]:
        return getattr(self.body, "action", None)

    def pre(self) -> dict[str, Any]:
        return getattr(self.body, "pre", {}) or {}

    # ----- on-disk serialization (spec §2.2) ----------------------------- #
    # Five files under gem/.  success is *excluded* (it lives in a note).
    def to_files(self) -> dict[str, bytes]:
        meta = {
            "kind": self.kind.value,
            "provenance": asdict(self.provenance),
            "cost": asdict(self.cost),
            "reversibility_class": self.reversibility_class.value,
            "consumed": list(self.consumed),
            "incited_by": self.incited_by,
        }
        body = _body_to_dict(self.body)
        index = asdict(self.index_keys)
        pre = self.pre()
        reasoning = self.reasoning_text()
        return {
            "gem/meta.json": _dump(meta),
            "gem/body.json": _dump(body),
            "gem/reasoning.md": reasoning.encode("utf-8"),
            "gem/pre.json": _dump(pre),
            "gem/index.json": _dump(index),
        }

    @classmethod
    def from_files(
        cls,
        files: dict[str, bytes],
        *,
        sha: Optional[str] = None,
        parents: Optional[list[str]] = None,
    ) -> "Gem":
        meta = json.loads(files["gem/meta.json"])
        body_d = json.loads(files["gem/body.json"])
        index = json.loads(files["gem/index.json"])
        reasoning = files.get("gem/reasoning.md", b"").decode("utf-8")
        kind = Kind(meta["kind"])
        body = _body_from_dict(kind, body_d, reasoning)
        gem = cls(
            kind=kind,
            provenance=Provenance(**meta["provenance"]),
            body=body,
            cost=Cost(**meta.get("cost", {})),
            reversibility_class=Reversibility(meta["reversibility_class"]),
            index_keys=IndexKeys(**index),
            consumed=list(meta.get("consumed", [])),
            incited_by=meta.get("incited_by"),
            id=sha,
            parents=list(parents or []),
        )
        return gem


# --------------------------------------------------------------------------- #
# Body (de)serialization helpers
# --------------------------------------------------------------------------- #
def _body_to_dict(body: Body) -> dict[str, Any]:
    if isinstance(body, DecisionBody):
        return {
            "type": "decision",
            "action": asdict(body.action),
            "tests": [asdict(t) for t in body.tests],
            "pre": body.pre,
            # reasoning is stored in reasoning.md, not duplicated here
        }
    if isinstance(body, KnowledgeBody):
        return {
            "type": "knowledge",
            "action": asdict(body.action),
            "belief": body.belief,
            "credence": body.credence,
            "tests": [asdict(t) for t in body.tests],
            "pre": body.pre,
        }
    if isinstance(body, ObservationBody):
        return {"type": "observation", "content": body.content, "pre": body.pre}
    raise TypeError(f"unknown body type {type(body).__name__}")


def _body_from_dict(kind: Kind, d: dict[str, Any], reasoning: str) -> Body:
    if kind is Kind.decision:
        return DecisionBody(
            action=Action(**d["action"]),
            reasoning=reasoning,
            tests=[TestSpec(**t) for t in d.get("tests", [])],
            pre=d.get("pre", {}),
        )
    if kind is Kind.knowledge:
        return KnowledgeBody(
            action=Action(**d["action"]),
            reasoning=reasoning,
            belief=d.get("belief", ""),
            credence=d.get("credence", 0.5),
            tests=[TestSpec(**t) for t in d.get("tests", [])],
            pre=d.get("pre", {}),
        )
    if kind is Kind.observation:
        return ObservationBody(
            content=d.get("content", ""), reasoning=reasoning, pre=d.get("pre", {})
        )
    raise ValueError(f"unknown kind {kind}")


def _dump(obj: Any) -> bytes:
    # sorted keys -> stable bytes -> stable content hashes for identical gems
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
