#!/usr/bin/env python3
"""``gemmery capture`` — commit a gem (spec §4, §11.1).

Intentional capture (Invariant 5): you call this deliberately after a decision
with a checkable outcome, or when acquiring a fact worth its future track
record.  Read ``references/schema.md`` before your first capture.

Usage:
    python scripts/capture.py spec.json          # from a file
    echo '{...}' | python scripts/capture.py -    # from stdin

The spec is JSON; minimal decision example:
    {
      "kind": "decision",
      "action": {"name": "add_db_index", "args": {"col": "user_id"}},
      "reasoning": "Why this, and which feature it would break on.",
      "tests": [{"id": "perf_p95", "how_to_run": "pytest -k p95", "what_counts": "p95<200ms"}],
      "pre": {"slow_query": true, "large_table": true},
      "precondition_shape": ["slow_query", "large_table", "index"],
      "action_type": "index_lookup",
      "domain": ["database"],
      "reversibility": "reversible",
      "consumed": []          # sha[] of gems this used — credit depends on it
    }
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from gemmery.cli import main  # noqa: E402

if __name__ == "__main__":
    args = sys.argv[1:] or ["-"]
    raise SystemExit(main(["capture", *args]))
