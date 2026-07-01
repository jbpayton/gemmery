"""Compute budget + membrane permeability for the browse loop (spec §6).

The budget is the load-bearing scientific control.  Browsing is *extra model
calls* (reformulate + assess each iteration), and extra test-time compute was
the only lever GitOfThoughts found that reliably helped (spec §0).  So Phase 0's
kill-switch control (browse + empty memory) runs the **same loop at the same
budget** — only the store is empty.  If the memory arm can't beat that, memory
is not load-bearing.  Therefore budget accounting must be exact and counted in
*model calls and tokens*, not loop iterations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Permeability(str, Enum):
    """Membrane between branches (spec §6.2). Default sealed."""

    sealed = "sealed"  # divergent exploration; no cross-reading sibling frontiers
    open = "open"  # synthesis; abandoned branches may be cross-read


@dataclass
class BudgetMeter:
    """Tracks model-call and token spend against a ceiling.

    The ceiling is a *ceiling*, not a target: an arm that satisfies early and
    spends less still counts as a win (a stronger one — spec §10.4).  The
    harness gives every arm the same ceiling and reports actual spend.
    """

    max_calls: Optional[int] = None
    max_tokens: Optional[int] = None
    calls: int = 0
    tokens: int = 0
    # per-purpose breakdown for the compute report (spec §10.4)
    by_purpose: dict[str, int] = field(default_factory=dict)

    def charge(self, *, calls: int = 1, tokens: int = 0, purpose: str = "") -> None:
        self.calls += calls
        self.tokens += tokens
        if purpose:
            self.by_purpose[purpose] = self.by_purpose.get(purpose, 0) + calls

    @property
    def exhausted(self) -> bool:
        if self.max_calls is not None and self.calls >= self.max_calls:
            return True
        if self.max_tokens is not None and self.tokens >= self.max_tokens:
            return True
        return False

    def can_afford(self, calls: int = 1) -> bool:
        if self.max_calls is None:
            return True
        return self.calls + calls <= self.max_calls

    def snapshot(self) -> dict:
        return {
            "calls": self.calls,
            "tokens": self.tokens,
            "max_calls": self.max_calls,
            "max_tokens": self.max_tokens,
            "by_purpose": dict(self.by_purpose),
        }
