#!/usr/bin/env python3
"""``gemmery promote`` — operator induction (spec §8).

GATED.  Inert until ``credit`` produces a stable signal (which is itself gated on
a replicated Phase-0 win).  Operator promotion is *the* answer to the
GitOfThoughts null, so it must not be built on an unverified premise (spec §8,
§10).

When the gate clears, this will cluster gems by precondition shape + action
type, partition heterogeneous regions by information-gain on the *credit signal*,
and emit near-executable operators (a precondition mask to match + a typed action
to bind) onto the ``operators`` branch.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from gemmery.operators import GATE  # noqa: E402

if __name__ == "__main__":
    print(GATE)
    print("Gate order:  Phase 0 (run_phase0)  ->  credit/  ->  operators/")
    sys.exit(2)
