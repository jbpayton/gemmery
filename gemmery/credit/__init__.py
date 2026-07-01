"""``credit/`` — earned, signed, deferred credit propagation (spec §7).

GATED.  Build only after the Phase 0 kill-switch (``eval``, spec §10) clears a
*replicated* win over the empty-memory control at matched compute.  Until then
this is a documented stub: the schema (valuation notes, dependency edges) is
already in place so credit can be layered on without touching captured gems.

Planned surface (do not implement before the gate):
  * ``propagate(store, resolved_sha, test, score, lam, max_depth)`` — flow signed
    credit backward along dependency edges, damped by an eligibility-trace
    horizon (§7.2).
  * ``resolve_dangling(store, sha, test, score)`` — turn a ``pending`` bet into a
    track record; enqueue the credit update as its own logged decision (§7.3).
  * ``why_aware_transfer(...)`` — extrapolate credit past sampled support using
    the ``reasoning`` field (§7.4).
"""

GATE = (
    "credit/ is gated behind a replicated Phase-0 win over the empty-memory "
    "control at matched compute (spec §10.3). Not implemented in v0.1."
)


def _gated(*_a, **_k):
    raise NotImplementedError(GATE)


propagate = _gated
resolve_dangling = _gated
why_aware_transfer = _gated
