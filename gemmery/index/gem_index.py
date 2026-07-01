"""``index/`` — derived, disposable retrieval index (spec §5).

Two layers, both rebuildable from ``store`` in one pass over commits:

1. **Columnar field index** (SQLite) — fast pre-filter on structured handles:
   ``action_type``, precondition-shape tokens, ``test_id``, ``reversibility_class``,
   signed ``credit``, outcome tag, recency.
2. **Embedding index** — embeddings of the ``reasoning`` trace and of the
   **precondition-shape** (solution/method shape — the GitOfThoughts escape),
   keyed by sha.

**Hybrid retrieval contract (the rule that matters):** pre-filter columnar,
*then* semantic over the survivors.  Never semantic-search the whole store cold.
When the caller supplies no structured filter, we still pre-filter via a cheap
lexical keyword narrowing before the embedding re-rank.

:meth:`GemIndex.rebuild` reconstructs both layers from git alone and asserts
parity (``indexed == commits``).  That assertion is a test (Invariant 6).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

import numpy as np

from ..model import Gem
from .embedder import Embedder, default_embedder

_FIELDS = ("reasoning", "pre")


@dataclass
class Hit:
    sha: str
    score: float  # semantic similarity (cosine) of the winning query/field
    field: str
    via_query: str


class GemIndex:
    def __init__(self, db_path: str = ":memory:", embedder: Optional[Embedder] = None):
        self.embedder = embedder or default_embedder()
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self._init_schema()
        # In-memory vector cache: {field: {sha: np.ndarray}}
        self._vecs: dict[str, dict[str, np.ndarray]] = {f: {} for f in _FIELDS}

    # ------------------------------------------------------------------ #
    # schema
    # ------------------------------------------------------------------ #
    def _init_schema(self) -> None:
        c = self.db
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS gems(
                sha TEXT PRIMARY KEY,
                kind TEXT, action_type TEXT, precondition_shape TEXT,
                domain TEXT, test_ids TEXT, reversibility_class TEXT,
                reasoning TEXT, credit REAL, ts REAL
            );
            CREATE TABLE IF NOT EXISTS gem_pre_tokens(sha TEXT, token TEXT);
            CREATE TABLE IF NOT EXISTS gem_tests(sha TEXT, test_id TEXT);
            CREATE TABLE IF NOT EXISTS gem_domain(sha TEXT, tag TEXT);
            CREATE TABLE IF NOT EXISTS outcomes(sha TEXT, test TEXT, ok INTEGER);
            CREATE TABLE IF NOT EXISTS embeddings(sha TEXT, field TEXT, vec BLOB);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX IF NOT EXISTS i_pre ON gem_pre_tokens(token);
            CREATE INDEX IF NOT EXISTS i_test ON gem_tests(test_id);
            CREATE INDEX IF NOT EXISTS i_dom ON gem_domain(tag);
            CREATE INDEX IF NOT EXISTS i_action ON gems(action_type);
            CREATE INDEX IF NOT EXISTS i_out ON outcomes(test, ok);
            """
        )
        c.execute(
            "INSERT OR REPLACE INTO meta(key,value) VALUES('embedder',?)",
            (self.embedder.name,),
        )
        c.commit()

    # ------------------------------------------------------------------ #
    # build / refresh
    # ------------------------------------------------------------------ #
    def add(self, gem: Gem, store) -> None:
        """Index (or re-index) a single gem from its in-memory form + store."""
        sha = gem.id
        assert sha, "gem must be captured (have an id) before indexing"
        ik = gem.index_keys
        pre_tokens = list(ik.precondition_shape)
        credit = store.notes(sha)["credit"]["total"]
        reasoning = gem.reasoning_text()

        c = self.db
        for tbl in ("gems", "gem_pre_tokens", "gem_tests", "gem_domain", "embeddings"):
            c.execute(f"DELETE FROM {tbl} WHERE sha=?", (sha,))
        c.execute(
            "INSERT INTO gems VALUES(?,?,?,?,?,?,?,?,?,?)",
            (sha, gem.kind.value, ik.action_type, " ".join(pre_tokens),
             " ".join(ik.domain), ",".join(t.id for t in gem.tests()),
             gem.reversibility_class.value, reasoning, credit,
             gem.provenance.timestamp),
        )
        c.executemany("INSERT INTO gem_pre_tokens VALUES(?,?)",
                      [(sha, t) for t in pre_tokens])
        c.executemany("INSERT INTO gem_tests VALUES(?,?)",
                      [(sha, t.id) for t in gem.tests()])
        c.executemany("INSERT INTO gem_domain VALUES(?,?)",
                      [(sha, t) for t in ik.domain])

        # embeddings: reasoning trace + precondition shape (solution-shape index)
        pre_text = " ".join(pre_tokens) + " " + ik.action_type
        vecs = self.embedder.embed([reasoning, pre_text])
        for field, vec in zip(_FIELDS, vecs):
            c.execute("INSERT INTO embeddings VALUES(?,?,?)",
                      (sha, field, vec.astype(np.float32).tobytes()))
            self._vecs[field][sha] = vec.astype(np.float32)
        c.commit()

    def refresh_valuation(self, sha: str, store) -> None:
        """Re-pull mutable valuation (credit/outcomes) for one gem (notes drift)."""
        credit = store.notes(sha)["credit"]["total"]
        self.db.execute("UPDATE gems SET credit=? WHERE sha=?", (credit, sha))
        self.db.commit()

    def rebuild(self, store) -> int:
        """Reconstruct both layers from git alone; assert parity (Invariant 6)."""
        c = self.db
        for tbl in ("gems", "gem_pre_tokens", "gem_tests", "gem_domain",
                    "outcomes", "embeddings"):
            c.execute(f"DELETE FROM {tbl}")
        for f in _FIELDS:
            self._vecs[f].clear()
        n = 0
        for gem in store.iter_gems():
            self.add(gem, store)
            n += 1
        # outcome tags
        for kind, test, sha in store.iter_outcome_tags():
            c.execute("INSERT INTO outcomes VALUES(?,?,?)",
                      (sha, test, 1 if kind == "ok" else 0))
        c.commit()
        indexed = c.execute("SELECT COUNT(*) FROM gems").fetchone()[0]
        commits = store.count_commits()
        assert indexed == commits, (
            f"index/store parity violated: {indexed} indexed != {commits} commits "
            "(the index must be fully rebuildable from git — Invariant 6)"
        )
        return n

    def load_vectors(self) -> None:
        """Repopulate the in-memory vector cache from the persisted blobs."""
        for f in _FIELDS:
            self._vecs[f].clear()
        for row in self.db.execute("SELECT sha, field, vec FROM embeddings"):
            vec = np.frombuffer(row["vec"], dtype=np.float32)
            self._vecs[row["field"]][row["sha"]] = vec

    # ------------------------------------------------------------------ #
    # columnar pre-filter (spec §5 layer 1)
    # ------------------------------------------------------------------ #
    def columnar_filter(
        self,
        *,
        kind: Optional[str] = None,
        action_type: Optional[str | Sequence[str]] = None,
        reversibility_class: Optional[str] = None,
        domain: Optional[str] = None,
        test_id: Optional[str] = None,
        min_credit: Optional[float] = None,
        max_credit: Optional[float] = None,
        outcome: Optional[str] = None,  # 'ok' | 'fail'
        since_ts: Optional[float] = None,
        pre_any: Optional[Sequence[str]] = None,
        pre_all: Optional[Sequence[str]] = None,
    ) -> list[str]:
        where = ["1=1"]
        params: list = []
        if kind:
            where.append("g.kind=?"); params.append(kind)
        if action_type:
            ats = [action_type] if isinstance(action_type, str) else list(action_type)
            where.append(f"g.action_type IN ({','.join('?' * len(ats))})"); params += ats
        if reversibility_class:
            where.append("g.reversibility_class=?"); params.append(reversibility_class)
        if min_credit is not None:
            where.append("g.credit >= ?"); params.append(min_credit)
        if max_credit is not None:
            where.append("g.credit <= ?"); params.append(max_credit)
        if since_ts is not None:
            where.append("g.ts >= ?"); params.append(since_ts)
        if domain:
            where.append("g.sha IN (SELECT sha FROM gem_domain WHERE tag=?)")
            params.append(domain)
        if test_id:
            where.append("g.sha IN (SELECT sha FROM gem_tests WHERE test_id=?)")
            params.append(test_id)
        if outcome:
            ok = 1 if outcome == "ok" else 0
            where.append("g.sha IN (SELECT sha FROM outcomes WHERE ok=?)")
            params.append(ok)
        if pre_any:
            where.append(
                "g.sha IN (SELECT sha FROM gem_pre_tokens WHERE token IN "
                f"({','.join('?' * len(pre_any))}))"
            )
            params += list(pre_any)
        if pre_all:
            for tok in pre_all:
                where.append("g.sha IN (SELECT sha FROM gem_pre_tokens WHERE token=?)")
                params.append(tok)
        sql = f"SELECT g.sha FROM gems g WHERE {' AND '.join(where)}"
        return [r["sha"] for r in self.db.execute(sql, params)]

    def _lexical_candidates(self, query: str, cap: int = 500) -> list[str]:
        """Cheap keyword narrowing when no structured filter is given."""
        from .embedder import _WORD

        toks = list(dict.fromkeys(_WORD.findall(query.lower())))
        if not toks:
            return [r["sha"] for r in self.db.execute("SELECT sha FROM gems LIMIT ?", (cap,))]
        shas: set[str] = set()
        ph = ",".join("?" * len(toks))
        for sql in (
            f"SELECT sha FROM gem_pre_tokens WHERE token IN ({ph})",
            f"SELECT sha FROM gems WHERE action_type IN ({ph})",
            f"SELECT sha FROM gem_domain WHERE tag IN ({ph})",
        ):
            shas.update(r["sha"] for r in self.db.execute(sql, toks))
        # reasoning LIKE for each token (coarse but cheap at eval scale)
        for tok in toks:
            for r in self.db.execute(
                "SELECT sha FROM gems WHERE reasoning LIKE ?", (f"%{tok}%",)
            ):
                shas.add(r["sha"])
            if len(shas) >= cap:
                break
        return list(shas)[:cap]

    # ------------------------------------------------------------------ #
    # semantic re-rank (spec §5 layer 2)
    # ------------------------------------------------------------------ #
    def _ensure_vectors(self) -> None:
        if not any(self._vecs[f] for f in _FIELDS):
            self.load_vectors()

    def semantic(self, query: str, candidates: Sequence[str], *,
                 field: str = "reasoning", top_k: int = 10) -> list[tuple[str, float]]:
        self._ensure_vectors()
        cache = self._vecs[field]
        cand = [s for s in candidates if s in cache]
        if not cand:
            return []
        mat = np.stack([cache[s] for s in cand])  # (n, dim), normalized
        q = self.embedder.embed([query])[0]
        scores = mat @ q  # cosine (rows + q normalized)
        order = np.argsort(-scores)[:top_k]
        return [(cand[i], float(scores[i])) for i in order]

    # ------------------------------------------------------------------ #
    # the hybrid contract (spec §5) — pre-filter THEN semantic
    # ------------------------------------------------------------------ #
    def hybrid_retrieve(
        self,
        queries: str | Sequence[str],
        *,
        filters: Optional[dict] = None,
        field: str = "reasoning",
        top_k: int = 10,
        restrict: Optional[set] = None,
    ) -> list[Hit]:
        """Columnar pre-filter, then semantic over survivors. Never cold.

        ``queries`` may be several reformulated surface forms (the browse loop
        issues 2-4); results are merged keeping the best score per sha.
        ``restrict`` (used by the browse membrane, spec §6.2) intersects the
        candidate set to an allowlist of shas before the semantic step.
        """
        if isinstance(queries, str):
            queries = [queries]

        best: dict[str, Hit] = {}
        for q in queries:
            if filters:
                candidates = self.columnar_filter(**filters)
            else:
                # No structured filter -> still pre-filter lexically (contract).
                candidates = self._lexical_candidates(q)
            if restrict is not None:
                candidates = [s for s in candidates if s in restrict]
            for fld in ({field} if isinstance(field, str) else set(field)):
                for sha, score in self.semantic(q, candidates, field=fld, top_k=top_k):
                    prev = best.get(sha)
                    if prev is None or score > prev.score:
                        best[sha] = Hit(sha=sha, score=score, field=fld, via_query=q)
        return sorted(best.values(), key=lambda h: -h.score)[:top_k]

    # ------------------------------------------------------------------ #
    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM gems").fetchone()[0]
