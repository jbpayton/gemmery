"""Shared store/index helpers for the skill scripts (spec §11.1).

Thin re-export over ``gemmery.cli`` so every script opens the *same* store and
index rather than re-implementing location logic.  The store path is
``$GEMMERY_STORE`` or ``./.gemmery-store``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running the scripts directly (python scripts/store.py) without install.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from gemmery.cli import open_index, open_store, store_path  # noqa: E402

__all__ = ["open_store", "open_index", "store_path"]
