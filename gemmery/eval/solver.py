"""Task solvers for the Phase-0 arms (spec §10).

A solver turns ``(task, recognized marks)`` into a signed per-test success score
(Invariant 2).  Two solvers:

* :class:`SimulatedSolver` — a *transparent model of the hypothesis*, not a rigged
  win.  Its only knob is ``transfer_gain``: the probability that recognizing a
  method-matching gem converts a task the solver would otherwise fail into a
  success.  With ``transfer_gain=0`` memory is inert and the harness MUST fail to
  green-light — that the harness can return "no" is exactly what makes it a
  kill-switch (spec §0).  Recognition itself is decided by the *real* retrieval
  code, so arm differences emerge from actual browse-vs-one-shot behavior, not
  from the solver.
* :class:`AnthropicSolver` — asks Claude to solve the task given the retrieved
  gems, then runs the real verifier.  This is the path for the actual efficacy
  run (pin the model id; charge real tokens for the matched-compute report).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional, Sequence

from ..browse.budget import BudgetMeter
from ..browse.policy import Mark
from .dataset import Task, Verifier


# --------------------------------------------------------------------------- #
# Real verifier execution (the bound test). NOTE: exec runs candidate code; the
# canonical solutions here are first-party. A real run with model-written code
# should sandbox this (subprocess + rlimits / container).
# --------------------------------------------------------------------------- #
def run_verifier(code: str, verifier: Verifier) -> float:
    """Run a candidate ``code`` string against a verifier. Returns +1.0/0.0.

    Signed (Invariant 2): pass -> +1.0; fail/exception -> 0.0 (present-inert).
    A solver may return a negative score for *harmful* output; the verifier
    itself never assigns negative (a failing test is inert, not harmful).
    """
    ns: dict = {}
    try:
        exec(code, ns)  # noqa: S102 - first-party canonical code in tests
        fn = ns[verifier.entry_point]
        for args, expected in verifier.cases:
            if fn(*args) != expected:
                return 0.0
        return 1.0
    except Exception:
        return 0.0


def grade(verifier, code: str) -> tuple[float, bool]:
    """Uniform grading across verifier types -> (score in [0,1], success bool).

    Supports the v2 :class:`~gemmery.eval.tasks_v2.ScoredVerifier` (continuous,
    objective-scored; success = score >= threshold) and the v1 exact-match
    ``Verifier`` (success = all cases pass).
    """
    if hasattr(verifier, "harness"):  # ScoredVerifier (objective-scored)
        s = verifier.score(code)
        return s, s >= verifier.threshold
    s = run_verifier(code, verifier)  # v1 exact-match
    return s, s >= 1.0


@dataclass
class SolveOutcome:
    scores: dict[str, float]  # test_id -> signed score
    method_recognized: bool
    used_marks: list[str]


def _deterministic_unit(*parts: str) -> float:
    """A stable pseudo-random number in [0,1) from inputs (no global RNG)."""
    h = hashlib.blake2b("::".join(parts).encode(), digest_size=8).digest()
    return int.from_bytes(h, "little") / 2 ** 64


class Solver:
    def solve(self, task: Task, marks: Sequence[Mark], store, meter: BudgetMeter,
              *, trial_key: str) -> SolveOutcome:  # pragma: no cover - interface
        raise NotImplementedError


class SimulatedSolver(Solver):
    def __init__(self, transfer_gain: float = 0.5, base_rate: float = 0.30,
                 solve_call_tokens: int = 800, best_of: int = 1):
        self.transfer_gain = transfer_gain
        self.base_rate = base_rate
        self.solve_call_tokens = solve_call_tokens
        # best_of>1 models spending freed budget on extra solve attempts — the
        # "more test-time compute helps" lever the one-shot arm must be allowed
        # so a memory 'win' can't be a relabeled compute win (spec §10.4).
        self.best_of = best_of

    def _method_recognized(self, task: Task, marks, store) -> tuple[bool, list[str]]:
        used = []
        recognized = False
        for m in marks:
            try:
                gem = store.read_gem(m.sha)
            except KeyError:
                continue
            used.append(m.sha)
            # action_type carries the schema id; domain carries the surface.
            if gem.index_keys.action_type == task.schema_id:
                # genuine transfer = same method, *different* surface
                if task.surface_domain not in gem.index_keys.domain:
                    recognized = True
        return recognized, used

    def solve(self, task, marks, store, meter, *, trial_key) -> SolveOutcome:
        recognized, used = self._method_recognized(task, marks, store)
        p = self.base_rate + (self.transfer_gain * (1 - self.base_rate) if recognized else 0.0)
        success = False
        for k in range(self.best_of):
            # Each attempt pays the same fixed solve cost -> compute differences
            # between arms come from retrieval + #attempts, never hidden.
            meter.charge(calls=1, tokens=self.solve_call_tokens, purpose="solve")
            if _deterministic_unit(trial_key, task.id, str(k)) < p:
                success = True
                break
        tid = task.verifier.test_id if task.verifier else f"unit::{task.id}"
        return SolveOutcome(scores={tid: 1.0 if success else 0.0},
                            method_recognized=recognized, used_marks=used)


class AnthropicSolver(Solver):
    """Solve with Claude using the retrieved gems, then run the real verifier."""

    def __init__(self, model: str = "claude-opus-4-8", client=None,
                 best_of: int = 1, max_tokens: int = 1500):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.best_of = best_of  # arm 2 can spend freed browse budget on best-of-k
        self.max_tokens = max_tokens

    def _context(self, marks, store) -> str:
        chunks = []
        for m in marks[:6]:
            try:
                gem = store.read_gem(m.sha)
            except KeyError:
                continue
            chunks.append(f"- past method ({gem.index_keys.action_type}): "
                          f"{gem.reasoning_text()[:400]}")
        return "\n".join(chunks) or "(no relevant memory)"

    def solve(self, task, marks, store, meter, *, trial_key) -> SolveOutcome:
        if not task.verifier:
            raise ValueError(f"task {task.id} has no runnable verifier")
        ctx = self._context(marks, store)
        prompt = task.prompt() if hasattr(task, "prompt") else task.problem_text
        sys = (
            "You are solving a programming task. You may reuse the approach from "
            "the retrieved memory if it applies. Return only a Python code block "
            "defining exactly what the task asks for."
        )
        user = f"Task:\n{prompt}\n\nRetrieved memory (past approaches):\n{ctx}"
        best = 0.0
        for _ in range(self.best_of):
            msg = self.client.messages.create(
                model=self.model, max_tokens=self.max_tokens, system=sys,
                messages=[{"role": "user", "content": user}],
            )
            usage = getattr(msg, "usage", None)
            tokens = (usage.input_tokens + usage.output_tokens) if usage else 0
            meter.charge(calls=1, tokens=tokens, purpose="solve")
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            code = _extract_code(text)
            score, success = grade(task.verifier, code)
            best = max(best, score)
            if success:
                break
        recognized = ctx != "(no relevant memory)"
        return SolveOutcome(scores={task.verifier.test_id: best},
                            method_recognized=recognized,
                            used_marks=[m.sha for m in marks])


def _extract_code(text: str) -> str:
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            body = parts[1]
            if body.startswith("python"):
                body = body[len("python"):]
            return body.strip()
    return text.strip()
