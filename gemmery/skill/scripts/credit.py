#!/usr/bin/env python3
"""``gemmery credit`` — earned, signed, deferred credit (spec §7).

GATED.  This command is intentionally inert until the Phase-0 kill-switch
(``python -m gemmery.eval.run_phase0``) clears a *replicated* win over the
empty-memory control at matched compute (spec §10.3, §14.6).  Building credit
propagation on unverified memory would be exactly the mistake Phase 0 exists to
prevent.

When the gate clears, this will: resolve dangling ``pending`` bets into track
records (§7.3) and propagate signed credit backward along dependency edges,
damped by an eligibility horizon (§7.2).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from gemmery.credit import GATE  # noqa: E402

if __name__ == "__main__":
    print(GATE)
    print("Run the kill-switch first:  python -m gemmery.eval.run_phase0")
    sys.exit(2)
