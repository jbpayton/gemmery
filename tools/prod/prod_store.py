"""The live dogfood store for this repo: .gemmery-store/ (gitignored).

Judgment layer only: gems hold rules, rationale, and citations into the raw
record (files, commits, transcripts) — never restatements of it.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
STORE_PATH = REPO / ".gemmery-store"
OUTCOMES = STORE_PATH / "outcomes.jsonl"
LOG = STORE_PATH / "librarian.log"


def get_store():
    from gemmery import GitStore
    return GitStore(STORE_PATH)


def dossiers(store):
    """[(path, tip_sha, gem)] for every knowledge/ dossier at main tip."""
    out = []
    try:
        entries = store.ls("knowledge")
    except Exception:
        return out
    for e in sorted(entries):
        name = e.rstrip("/")
        path = f"knowledge/{name}"
        hist = store.history(path)
        if hist:
            out.append((path, hist[0], store.read_gem(hist[0])))
    return out
