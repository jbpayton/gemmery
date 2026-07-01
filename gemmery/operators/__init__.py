"""``operators/`` — promotion: manufacturing copyability (spec §8).

GATED.  Build only after ``credit`` produces a stable signal (which is itself
gated on Phase 0).  This is *the* answer to the GitOfThoughts null, not a
feature — so it must not be built on an unverified premise.

Planned surface (do not implement before the gate):
  * ``cluster(gems)`` — group concrete gems by precondition shape + action type.
  * ``partition_on_credit(cluster)`` — information-gain split on the *credit
    signal* (not class labels) where outcomes are heterogeneous (§8.2); the
    discriminating precondition feature becomes a new applicability condition.
  * ``induce_operator(partition)`` — emit a near-executable operator: a
    precondition mask to match + a typed action to bind (§8.3), stored on the
    ``operators`` branch and indexed by applicability mask.

Central knob (§8.2): the stopping rule. Too coarse re-imports "X fails" as
under-conditioning; too fine manufactures superstitions ("X fails on Tuesdays").
Require minimum-support AND a complexity penalty; expose stopping depth as a
tuned hyperparameter, never a constant.
"""

GATE = (
    "operators/ is gated behind a stable credit signal, itself gated on a "
    "replicated Phase-0 win (spec §8, §10). Not implemented in v0.1."
)


def _gated(*_a, **_k):
    raise NotImplementedError(GATE)


cluster = _gated
partition_on_credit = _gated
induce_operator = _gated
