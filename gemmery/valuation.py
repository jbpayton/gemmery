"""Mutable valuation over immutable gems (spec §2.3, Invariant 1).

Commits are never rewritten to add scores or credit.  Valuation is appended
out-of-band via ``git notes``.  We go one step further than git's default
"a note replaces the previous note": each note is an **append-only JSONL log**
of valuation events, and the current value is a *fold* over that log.  That
keeps the valuation history auditable too — "used in 12, vindicated in 9"
(spec §7.3) is recoverable, not just the latest number.

Two note refs:
  * ``refs/notes/success`` — per-test success events  -> a ``{test_id: score|⊥}`` map
  * ``refs/notes/credit``  — signed credit deltas      -> a running signed total

Both are three-valued aware: a test with only ``pending`` events folds to
:data:`gemmery.model.PENDING`, never to 0.0 (Invariant 3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Optional, Union

from .model import PENDING, Score, clamp_score

SUCCESS_REF = "refs/notes/success"
CREDIT_REF = "refs/notes/credit"
DEPS_REF = "refs/notes/deps"  # late-discovered dependency edges (spec §4)


# --------------------------------------------------------------------------- #
# Event encoding (one JSON object per line)
# --------------------------------------------------------------------------- #
def _line(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def parse_log(note_text: Optional[str]) -> list[dict]:
    if not note_text:
        return []
    out = []
    for raw in note_text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            # tolerate a stray non-JSON line rather than lose the whole log
            continue
    return out


def append_line(note_text: Optional[str], obj: dict) -> str:
    base = (note_text or "").rstrip("\n")
    line = _line(obj)
    return (base + "\n" + line).lstrip("\n") if base else line


# --------------------------------------------------------------------------- #
# Success log
# --------------------------------------------------------------------------- #
def success_pending_event(test_id: str, ts: float) -> dict:
    return {"test_id": test_id, "status": "pending", "ts": ts}


def success_score_event(test_id: str, score: float, ts: float, source: Optional[str] = None) -> dict:
    ev = {"test_id": test_id, "status": "scored", "score": clamp_score(score), "ts": ts}
    if source:
        ev["source"] = source
    return ev


@dataclass
class SuccessCell:
    """Folded value for one test: a signed score, or PENDING (⊥)."""

    value: Union[Score, object]  # float or PENDING
    n_scored: int = 0  # how many times this test was scored (track record)

    @property
    def is_pending(self) -> bool:
        return self.value is PENDING


def fold_success(note_text: Optional[str]) -> dict[str, SuccessCell]:
    """Reduce the success JSONL log to ``{test_id -> SuccessCell}``.

    Latest scored event wins per test; a test with only pending events folds to
    PENDING.  ``n_scored`` records the track record (vindication count signal).
    """
    log = parse_log(note_text)
    cells: dict[str, SuccessCell] = {}
    for ev in log:
        tid = ev.get("test_id")
        if tid is None:
            continue
        if ev.get("status") == "scored":
            cell = cells.get(tid)
            n = (cell.n_scored if cell else 0) + 1
            cells[tid] = SuccessCell(value=clamp_score(ev["score"]), n_scored=n)
        else:  # pending
            if tid not in cells:
                cells[tid] = SuccessCell(value=PENDING, n_scored=0)
    return cells


def success_summary(note_text: Optional[str]) -> dict[str, object]:
    """JSON-friendly view: ``{test_id: score|"pending"}`` plus track-record counts."""
    cells = fold_success(note_text)
    return {
        tid: ("pending" if c.is_pending else c.value) for tid, c in cells.items()
    }


# --------------------------------------------------------------------------- #
# Credit log  (signed, continuous — Invariant 2; §7)
# --------------------------------------------------------------------------- #
def credit_event(delta: float, ts: float, source: Optional[str] = None, test: Optional[str] = None) -> dict:
    ev = {"delta": float(delta), "ts": ts}
    if source:
        ev["source"] = source
    if test:
        ev["test"] = test
    return ev


@dataclass
class CreditSummary:
    total: float
    n_events: int
    by_source: dict[str, float]


def fold_credit(note_text: Optional[str]) -> CreditSummary:
    log = parse_log(note_text)
    total = 0.0
    by_source: dict[str, float] = {}
    for ev in log:
        d = float(ev.get("delta", 0.0))
        total += d
        src = ev.get("source") or "?"
        by_source[src] = by_source.get(src, 0.0) + d
    return CreditSummary(total=total, n_events=len(log), by_source=by_source)


# --------------------------------------------------------------------------- #
# Dependency-edge sidecar (late-discovered edges; capture-time edges live in
# meta.json `consumed[]`).  Append-only, auditable (spec §4).
# --------------------------------------------------------------------------- #
def dep_event(consumed_sha: str, role: str, ts: float) -> dict:
    return {"consumed": consumed_sha, "role": role, "ts": ts}


def fold_deps(note_text: Optional[str]) -> list[dict]:
    return parse_log(note_text)
