"""Derived, disposable retrieval index (spec §5). Rebuildable from git alone."""

from .embedder import (
    Embedder,
    HashingEmbedder,
    SentenceTransformerEmbedder,
    default_embedder,
)
from .gem_index import GemIndex, Hit

__all__ = [
    "Embedder",
    "HashingEmbedder",
    "SentenceTransformerEmbedder",
    "default_embedder",
    "GemIndex",
    "Hit",
]
