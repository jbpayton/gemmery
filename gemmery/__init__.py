"""Gemmery — versioned agent memory with earned, test-bound credit.

A gemmery is where rough stones are kept, cut, and turned into gems.  Captured
records are *gems* stored as an immutable, branchable git DAG; valuation is
appended out-of-band as git notes; retrieval is an intentional, agent-driven
*browse* loop rather than a one-shot lookup.

The build is **gated, not linear** (spec §0): Phase 0 (the ``eval`` kill-switch)
plus minimal ``store``/``index``/``browse`` come first.  ``credit``,
``operators`` and ``effects`` are stubs until Phase 0 clears its decision rule.
"""

from .model import (
    Action,
    Cost,
    DecisionBody,
    Gem,
    IndexKeys,
    Kind,
    KnowledgeBody,
    ObservationBody,
    PENDING,
    Provenance,
    Reversibility,
    TestSpec,
)
from .store import GitStore

__version__ = "0.1.0"

__all__ = [
    "Action",
    "Cost",
    "DecisionBody",
    "Gem",
    "GitStore",
    "IndexKeys",
    "Kind",
    "KnowledgeBody",
    "ObservationBody",
    "PENDING",
    "Provenance",
    "Reversibility",
    "TestSpec",
]
