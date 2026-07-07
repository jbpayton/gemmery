"""The production loop, shipped with the package (P3).

Three hook entry points wire any project into a living store:

* ``gemmery inject``       (SessionStart)  — earned dossiers into context
* ``gemmery outcome-hook`` (PostToolUse)   — pytest outcomes to the ledger
* ``gemmery librarian``    (SessionEnd)    — fold outcomes into credit, then
  distill the session into dossier ops (one cheap LLM call)

``gemmery init`` creates the store and wires the hooks. The store lives at
``<project>/.gemmery-store`` (or $GEMMERY_STORE); dossiers hold judgment with
citations into the raw record — the project itself — never restatements.
"""
import os
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("GEMMERY_ROOT")
    return Path(env) if env else Path.cwd()


def store_path() -> Path:
    env = os.environ.get("GEMMERY_STORE")
    return Path(env) if env else project_root() / ".gemmery-store"


def get_store():
    from ..store import GitStore
    return GitStore(store_path())


def dossiers(store):
    """[(path, tip_sha, gem)] for every knowledge/ dossier at main tip."""
    out = []
    try:
        entries = store.ls("knowledge")
    except Exception:
        return out
    for e in sorted(entries):
        path = f"knowledge/{e.rstrip('/')}"
        hist = store.history(path)
        if hist:
            out.append((path, hist[0], store.read_gem(hist[0])))
    return out
