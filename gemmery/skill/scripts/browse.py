#!/usr/bin/env python3
"""``gemmery browse`` — the agentic retrieval loop (spec §6, §11.1).

Browsing is recognition, not one-shot recall.  Drive the loop: it issues several
surface forms, pre-filters on handles, reads partials, and recognizes what
applies.  Read ``references/browse-patterns.md`` before nontrivial retrieval.

Usage:
    python scripts/browse.py "how did we handle transient retries" --budget 8
    python scripts/browse.py "<goal>" --permeability open   # synthesis mode

Note the budget is a hard ceiling on model calls — the same control the Phase-0
eval uses, so retrieval cost stays honest.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from gemmery.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["browse", *sys.argv[1:]]))
