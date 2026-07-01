"""``effects/`` — reversibility tracking + compensation/saga log (spec §9).

GATED (deferred to stub for v0.1, spec §14.1).  The *classification* already
lives on every gem (``Gem.reversibility_class``), so Phase 0 records it; the
compensation machinery below is the deferred part.

Key promise to keep honest (§9): git rewinds *state, not the world*
(Invariant 8).  The clean time-travel story holds only in the pure/reversible
deliberation sub-DAG.  ``compensable`` effects carry an inverse that a rewind
must trigger; ``irreversible`` effects make history and world diverge — flag
loudly, never silently "rewind".

Planned surface (do not implement before the gate):
  * ``register_compensation(store, forward_sha, inverse_action)`` — attach the
    undo to a compensable forward gem (saga log fused with the memory tree).
  * ``rewind(store, sha)`` — for the reversible zone, restore epistemic state;
    for compensable gems on the path, emit the compensating actions; refuse on
    irreversible gems with a loud error.
"""

from ..model import Reversibility

GATE = "effects/ compensation machinery is deferred to a stub in v0.1 (spec §14.1)."

# The reversibility zones (spec §9): pure/reversible is the freely-rewindable
# time-travel zone; compensable/irreversible is bounded by compensation.
FREELY_REWINDABLE = frozenset({Reversibility.pure, Reversibility.reversible})
REQUIRES_COMPENSATION = frozenset({Reversibility.compensable, Reversibility.irreversible})


def is_freely_rewindable(rc: Reversibility) -> bool:
    return Reversibility(rc) in FREELY_REWINDABLE


def _gated(*_a, **_k):
    raise NotImplementedError(GATE)


register_compensation = _gated
rewind = _gated
