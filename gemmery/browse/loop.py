"""The agentic browse loop (spec §6.1) — the crux of Gemmery.

Retrieval is **not** ``get_relevant(query) -> top_k`` injected once.  It is a
bounded loop the agent drives: reformulate into several surface forms, retrieve,
read partials, and *recognize* what applies — converting an impossible recall
problem into a tractable recognition problem (spec §0 escape #1).

This module is deliberately thin and policy-agnostic.  The intelligence lives in
the :class:`~gemmery.browse.policy.BrowsePolicy`; the loop's job is to enforce
the compute budget exactly (so the Phase-0 control is honest) and the membrane
permeability (so divergent exploration stays unbiased — spec §6.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..store import MAIN
from .budget import BudgetMeter, Permeability
from .policy import (
    BrowsePolicy,
    BrowseTools,
    Mark,
    MockPolicy,
    Partial,
    make_partial,
)


@dataclass
class BrowseStep:
    queries: list[str]
    hit_shas: list[str]
    satisfied: bool


@dataclass
class BrowseResult:
    marks: list[Mark]
    satisfied: bool
    iterations: int
    budget: dict  # meter snapshot — the matched-compute report (spec §10.4)
    transcript: list[BrowseStep] = field(default_factory=list)
    mode: str = "browse"

    @property
    def mark_shas(self) -> list[str]:
        # de-dup keeping best relevance
        best: dict[str, Mark] = {}
        for m in self.marks:
            if m.sha not in best or m.relevance > best[m.sha].relevance:
                best[m.sha] = m
        return [m.sha for m in sorted(best.values(), key=lambda x: -x.relevance)]


def _permeable_set(store, permeability: Permeability,
                   current_branch: Optional[str],
                   exclude: Optional[set[str]] = None) -> Optional[set[str]]:
    if permeability is Permeability.open:
        base = None  # no restriction; synthesis may cross-read frontiers
    else:
        refs = [MAIN]
        if current_branch and current_branch != MAIN:
            refs.append(current_branch)
        base = store.reachable_shas(refs)
    if exclude:
        # Leave-one-out: a query must transfer from a *different* gem, never copy
        # itself (the answer-copying failure mode GitOfThoughts found, §0).
        if base is None:
            base = set(store.all_shas())
        base = base - exclude
    return base


def browse(
    goal: str,
    *,
    store,
    index,
    policy: Optional[BrowsePolicy] = None,
    budget: Optional[BudgetMeter] = None,
    permeability: Permeability = Permeability.sealed,
    current_branch: Optional[str] = None,
    top_k: int = 8,
    max_iters: int = 6,
    filters: Optional[dict] = None,
    field: str = "reasoning",
    exclude: Optional[set[str]] = None,
) -> BrowseResult:
    """Run the bounded browse loop (spec §6.1).

    Stops when the policy is satisfied, the budget is exhausted, or ``max_iters``
    is hit.  Returns recognized marks plus the budget snapshot (so the harness
    can report the memory effect *after* equalizing compute — spec §10.4).
    """
    policy = policy or MockPolicy()
    meter = budget or BudgetMeter()
    restrict = _permeable_set(store, permeability, current_branch, exclude)
    tools = BrowseTools(store, index, restrict)

    seen: set[str] = set()
    all_marks: list[Mark] = []
    transcript: list[BrowseStep] = []
    cues = goal
    satisfied = False
    iterations = 0

    while not satisfied and iterations < max_iters:
        # Each iteration spends two model calls (reformulate + assess). Stop
        # before starting one we cannot fully afford, so the budget is a hard
        # ceiling (Invariant: matched compute is exact).
        if not meter.can_afford(2):
            break

        queries = policy.reformulate(cues, goal, meter)
        hits = index.hybrid_retrieve(
            queries, filters=filters, field=field, top_k=top_k, restrict=restrict
        )
        fresh = [h for h in hits if h.sha not in seen]
        seen.update(h.sha for h in fresh)
        partials: list[Partial] = [
            make_partial(store, h.sha, retrieval_score=h.score) for h in fresh
        ]

        result = policy.assess(partials, goal, meter, tools)
        all_marks.extend(result.marks)
        satisfied = result.satisfied
        cues = result.cues or goal
        transcript.append(BrowseStep(queries=queries,
                                     hit_shas=[h.sha for h in fresh],
                                     satisfied=satisfied))
        iterations += 1

    return BrowseResult(
        marks=all_marks, satisfied=satisfied, iterations=iterations,
        budget=meter.snapshot(), transcript=transcript, mode="browse",
    )


def one_shot(
    goal: str,
    *,
    store,
    index,
    top_k: int = 8,
    filters: Optional[dict] = None,
    field: str = "reasoning",
    permeability: Permeability = Permeability.sealed,
    current_branch: Optional[str] = None,
    budget: Optional[BudgetMeter] = None,
    exclude: Optional[set[str]] = None,
) -> BrowseResult:
    """The GitOfThoughts modality (eval arm 2): one static top-k lookup, no loop.

    This is the thing Gemmery claims is the *wrong* modality (spec §10.1).  It is
    provided so the harness can A/B it against :func:`browse` at matched compute.
    No model calls are made here (the single retrieval is injected once); any
    solve-side compute is charged by the harness, equally across arms.
    """
    meter = budget or BudgetMeter()
    restrict = _permeable_set(store, permeability, current_branch, exclude)
    hits = index.hybrid_retrieve(goal, filters=filters, field=field,
                                 top_k=top_k, restrict=restrict)
    marks = [Mark(sha=h.sha, reason="one-shot top-k", relevance=h.score) for h in hits]
    step = BrowseStep(queries=[goal], hit_shas=[h.sha for h in hits], satisfied=True)
    return BrowseResult(marks=marks, satisfied=True, iterations=1,
                        budget=meter.snapshot(), transcript=[step], mode="one_shot")
