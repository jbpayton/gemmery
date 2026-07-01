"""Pluggable embedding interface (spec §5, §12).

The index is derived and disposable (Invariant 6), and the embedder behind it is
swappable.  We ship two:

* :class:`HashingEmbedder` — dependency-free, deterministic across processes
  (uses blake2b, not Python's salted ``hash()``).  Cosine approximates token
  overlap.  This keeps the test suite offline and reproducible, and serves as a
  weak-but-honest baseline.
* :class:`SentenceTransformerEmbedder` — real semantic embeddings, used for the
  actual Phase-0 efficacy runs.  Optional dependency (``pip install
  'gemmery[embed]'``).

Crucially, *what* we embed is the GitOfThoughts escape (spec §5): the
``reasoning`` trace and the **precondition-shape**, i.e. solution/method shape —
not just problem surface.  The embedder is interchangeable; the indexed text is
the design commitment.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol, Sequence

import numpy as np

_WORD = re.compile(r"[a-z0-9_]+")


class Embedder(Protocol):
    dim: int

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Return an ``(n, dim)`` float32 array of L2-normalized rows."""
        ...

    @property
    def name(self) -> str:
        ...


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class HashingEmbedder:
    """Deterministic hashing-trick embedder (no model download required)."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    @property
    def name(self) -> str:
        return f"hashing-{self.dim}"

    def _features(self, text: str) -> list[str]:
        text = (text or "").lower()
        feats: list[str] = []
        for tok in _WORD.findall(text):
            feats.append(tok)
            # char trigrams give fuzzy overlap (typos, morphology)
            padded = f"#{tok}#"
            feats += [padded[i:i + 3] for i in range(len(padded) - 2)]
        return feats

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for r, text in enumerate(texts):
            for feat in self._features(text):
                h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(h[:4], "little") % self.dim
                sign = 1.0 if (h[4] & 1) else -1.0
                out[r, idx] += sign
        return _l2_normalize(out)


class SentenceTransformerEmbedder:
    """Real semantic embeddings via sentence-transformers (optional dep)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer  # lazy import

        self._model = SentenceTransformer(model_name)
        self._model_name = model_name
        self.dim = int(self._model.get_sentence_embedding_dimension())

    @property
    def name(self) -> str:
        return f"st-{self._model_name}"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        vecs = self._model.encode(list(texts), convert_to_numpy=True,
                                  normalize_embeddings=True)
        return vecs.astype(np.float32)


def default_embedder() -> Embedder:
    return HashingEmbedder()
