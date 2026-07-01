"""Git-native read/write layer (spec §4)."""

from .git_store import (
    GitStore,
    CaptureResult,
    MAIN,
    OPERATORS_BRANCH,
)

__all__ = ["GitStore", "CaptureResult", "MAIN", "OPERATORS_BRANCH"]
