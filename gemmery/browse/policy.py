"""Browse policies: how an agent reformulates and recognizes (spec §6).

The loop (``loop.py``) is fixed; the *policy* is the agent.  Two policies ship:

* :class:`MockPolicy` — deterministic, token-overlap based.  It exists for two
  reasons: (1) offline, reproducible tests; (2) the **fixed-agent baseline** the
  eval can hold constant across arms so the only difference is the store.
* :class:`AnthropicPolicy` — a real Claude-driven policy (optional dep; pin the
  model id for eval, spec §12).

A policy makes the loop's model calls and is responsible for charging the
:class:`~gemmery.browse.budget.BudgetMeter` for every call (and, for real LLMs,
the tokens).  Topology-walk primitives (pickaxe / tags / frontier / diff) are
git ops, *not* model calls — they are offered to ``assess`` via
:class:`BrowseTools` so a policy can walk the DAG, which a flat vector store
cannot (spec §6.1, the capability argument for git).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .budget import BudgetMeter

_WORD = re.compile(r"[a-z0-9_]+")
_STOP = frozenset(
    "the a an of to for and or in on with how do does is are be use using "
    "when where what which that this it as by from".split()
)


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall((text or "").lower()) if t not in _STOP}


@dataclass
class Partial:
    """A read gem, as seen by the recognition step."""

    sha: str
    kind: str
    action_name: str
    reasoning: str
    pre: dict
    precondition_shape: list[str]
    domain: list[str]
    success: dict
    credit: float
    retrieval_score: float = 0.0


@dataclass
class Mark:
    """A gem the agent recognized as applicable (spec §6 'recognized_marks')."""

    sha: str
    reason: str
    relevance: float


@dataclass
class AssessResult:
    cues: str  # next-iteration cues (content becomes the next query seed)
    satisfied: bool
    marks: list[Mark] = field(default_factory=list)


class BrowseTools:
    """Git-graph walk primitives a policy may call mid-assess (not model calls)."""

    def __init__(self, store, index, restrict: Optional[set[str]] = None):
        self._store = store
        self._index = index
        self._restrict = restrict

    def _ok(self, sha: str) -> bool:
        return self._restrict is None or sha in self._restrict

    def pickaxe(self, needle: str, *, regex: bool = False) -> list[str]:
        return [s for s in self._store.pickaxe(needle, regex=regex) if self._ok(s)]

    def by_tag(self, glob: str) -> list[str]:
        return self._store.by_tag(glob)

    def frontier(self, task: str) -> dict:
        return self._store.frontier(task)

    def diff(self, a: str, b: str, path: Optional[str] = None) -> str:
        return self._store.diff(a, b, path)

    def read(self, sha: str) -> Partial:
        return make_partial(self._store, sha)


def make_partial(store, sha: str, retrieval_score: float = 0.0) -> Partial:
    gem = store.read_gem(sha)
    notes = store.notes(sha)
    action = gem.action()
    return Partial(
        sha=sha,
        kind=gem.kind.value,
        action_name=action.name if action else "",
        reasoning=gem.reasoning_text(),
        pre=gem.pre(),
        precondition_shape=list(gem.index_keys.precondition_shape),
        domain=list(gem.index_keys.domain),
        success=notes["success"],
        credit=notes["credit"]["total"],
        retrieval_score=retrieval_score,
    )


# --------------------------------------------------------------------------- #
# Policy interface
# --------------------------------------------------------------------------- #
class BrowsePolicy(ABC):
    @abstractmethod
    def reformulate(self, cues: str, goal: str, meter: BudgetMeter) -> list[str]:
        """Return 2-4 surface forms of the need (problem- and solution-side)."""

    @abstractmethod
    def assess(self, partials: Sequence[Partial], goal: str, meter: BudgetMeter,
               tools: BrowseTools) -> AssessResult:
        """Recognition step: which partials apply, are we done, next cues."""


# --------------------------------------------------------------------------- #
# Deterministic mock policy (offline baseline)
# --------------------------------------------------------------------------- #
class MockPolicy(BrowsePolicy):
    def __init__(self, n_forms: int = 3, recognize_threshold: float = 0.18,
                 satisfied_threshold: float = 0.45):
        self.n_forms = n_forms
        self.recognize_threshold = recognize_threshold
        self.satisfied_threshold = satisfied_threshold

    def reformulate(self, cues: str, goal: str, meter: BudgetMeter) -> list[str]:
        meter.charge(calls=1, purpose="reformulate")
        base = cues or goal
        # problem-side and solution-side framings (spec §6.1)
        forms = [
            base,
            f"how to solve: {base}",
            f"operator that applies when {base}",  # solution/method-shape framing
            f"precondition: {base}",
        ]
        # de-dup, keep order
        seen, out = set(), []
        for f in forms:
            if f not in seen:
                seen.add(f); out.append(f)
        return out[: self.n_forms]

    def _relevance(self, p: Partial, goal_toks: set[str]) -> float:
        hay = _tokens(
            p.action_name + " " + " ".join(p.precondition_shape)
            + " " + " ".join(p.domain) + " " + p.reasoning
        )
        if not goal_toks or not hay:
            return 0.0
        overlap = len(goal_toks & hay) / len(goal_toks)
        # a small nudge from earned credit (a vindicated gem is more applicable)
        return min(1.0, overlap + 0.1 * max(0.0, p.credit))

    def assess(self, partials, goal, meter, tools) -> AssessResult:
        meter.charge(calls=1, purpose="assess")
        goal_toks = _tokens(goal)
        scored = [(p, self._relevance(p, goal_toks)) for p in partials]
        scored.sort(key=lambda x: -x[1])
        marks = [
            Mark(sha=p.sha, reason=f"precondition/action overlap={r:.2f}", relevance=r)
            for p, r in scored if r >= self.recognize_threshold
        ]
        best = scored[0][1] if scored else 0.0
        satisfied = best >= self.satisfied_threshold
        # next cues: seed from the best partial's reasoning (recognition→recall)
        cues = scored[0][0].reasoning if scored else goal
        return AssessResult(cues=cues, satisfied=satisfied, marks=marks)


# --------------------------------------------------------------------------- #
# Real Claude-driven policy (optional; for Phase-0 efficacy runs)
# --------------------------------------------------------------------------- #
class AnthropicPolicy(BrowsePolicy):
    """Claude-driven reformulate/assess. Requires ``pip install 'gemmery[llm]'``.

    Pin ``model`` for eval (spec §12).  Charges the meter with real token usage
    so the matched-compute report (spec §10.4) reflects actual spend.
    """

    def __init__(self, model: str = "claude-opus-4-8", client=None, n_forms: int = 3):
        if client is None:
            import anthropic  # lazy import

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.n_forms = n_forms

    def _ask(self, system: str, user: str, meter: BudgetMeter, purpose: str,
             max_tokens: int = 512) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        used = getattr(msg, "usage", None)
        tokens = (used.input_tokens + used.output_tokens) if used else 0
        meter.charge(calls=1, tokens=tokens, purpose=purpose)
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    def reformulate(self, cues, goal, meter) -> list[str]:
        out = self._ask(
            system=(
                "You help an agent search a memory of past solutions. Given a need, "
                "emit 2-4 short search queries as surface forms — include both "
                "problem-side phrasings and solution/method-shape phrasings. "
                "One query per line, no numbering."
            ),
            user=f"Goal: {goal}\nCurrent cues: {cues}",
            meter=meter, purpose="reformulate",
        )
        forms = [ln.strip("-• \t") for ln in out.splitlines() if ln.strip()]
        return forms[: self.n_forms] or [cues or goal]

    def assess(self, partials, goal, meter, tools) -> AssessResult:
        listing = "\n\n".join(
            f"[{i}] sha={p.sha[:10]} action={p.action_name} "
            f"pre={p.pre} credit={p.credit:.2f}\nreasoning: {p.reasoning[:400]}"
            for i, p in enumerate(partials)
        ) or "(no results)"
        out = self._ask(
            system=(
                "You are deciding which retrieved memory gems are APPLICABLE to the "
                "goal — recognition, not recall. For each clearly applicable gem, "
                "output a line 'MARK <index> <0-1 relevance> <one-clause why>'. "
                "If a strongly applicable gem is present, end with 'SATISFIED'. "
                "Otherwise end with 'NEXT: <refined cues>'."
            ),
            user=f"Goal: {goal}\n\nRetrieved:\n{listing}",
            meter=meter, purpose="assess",
        )
        marks: list[Mark] = []
        satisfied = "SATISFIED" in out.upper()
        next_cues = goal
        for ln in out.splitlines():
            s = ln.strip()
            if s.upper().startswith("MARK"):
                parts = s.split(None, 3)
                try:
                    idx = int(parts[1]); rel = float(parts[2])
                    if 0 <= idx < len(partials):
                        marks.append(Mark(partials[idx].sha,
                                          parts[3] if len(parts) > 3 else "", rel))
                except (ValueError, IndexError):
                    continue
            elif s.upper().startswith("NEXT:"):
                next_cues = s[5:].strip() or goal
        return AssessResult(cues=next_cues, satisfied=satisfied, marks=marks)
