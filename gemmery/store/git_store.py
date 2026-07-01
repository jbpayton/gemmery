"""``store/`` — git-native read/write (spec §4).

Git is the source of truth (Invariant 6).  Everything else (index, embeddings)
is derived and disposable.  This module is the *only* place that touches git.

Split by speed requirement:

* **Capture path** (Invariant 9, target < 25 ms): pure pygit2 — build the gem
  tree in memory, commit, write one ``pending`` success note.  No working-tree
  writes, no subprocess spawns.
* **Query path** (speed non-critical): subprocess ``git`` for pickaxe
  (``-S``/``-G``), ``--grep``, tag globs, and frontier diffs — operations pygit2
  exposes awkwardly.

Interpretation note (reconciling §2.1 and §2.2): a gem *commit's tree* holds the
five record files under ``gem/``.  The history-graph parent edge chains gems
into a reasoning path; the effect of a refinement is the git diff of the record
between a gem and its parent.  Checkout restores epistemic state (the gem + its
ancestry as data), not a working directory (Invariant 8).
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pygit2

from ..model import Gem, TestSpec
from ..valuation import (
    CREDIT_REF,
    DEPS_REF,
    SUCCESS_REF,
    append_line,
    credit_event,
    dep_event,
    fold_credit,
    fold_deps,
    success_pending_event,
    success_score_event,
    success_summary,
)

MAIN = "main"
OPERATORS_BRANCH = "operators"

GEM_FILES = (
    "meta.json",
    "body.json",
    "reasoning.md",
    "pre.json",
    "index.json",
)


@dataclass
class CaptureResult:
    sha: str
    branch: str
    capture_ms: float


class GitStore:
    """The git-backed gem store."""

    def __init__(self, path: str | Path, *, actor: str = "gemmery-agent",
                 email: str = "agent@gemmery.local"):
        self.path = Path(path)
        self._actor = actor
        self._email = email
        if (self.path / ".git").exists() or (self.path / "HEAD").exists():
            self.repo = pygit2.Repository(str(self.path))
        else:
            self.path.mkdir(parents=True, exist_ok=True)
            # Non-bare so a human can `git -C store log` to inspect; we never
            # touch the working tree on the capture path.
            self.repo = pygit2.init_repository(str(self.path), bare=False,
                                               initial_head=MAIN)

    # ------------------------------------------------------------------ #
    # Capture (the hot path)
    # ------------------------------------------------------------------ #
    def capture(self, gem: Gem, *, branch: str = MAIN,
                parents: Optional[list[str]] = None) -> CaptureResult:
        """Write a gem as one commit + a pending success note.

        Returns a :class:`CaptureResult` including the measured capture time so
        callers / tests can assert the < 25 ms invariant.
        """
        t0 = time.perf_counter()
        ref_name = f"refs/heads/{branch}"

        # Resolve parents: explicit > branch tip > orphan.
        if parents is None:
            tip = self._ref_target(ref_name)
            parent_oids = [tip] if tip is not None else []
        else:
            parent_oids = [pygit2.Oid(hex=p) for p in parents]

        tree_oid = self._build_tree(gem)
        sig = self._signature(gem)
        message = _commit_message(gem)

        commit_oid = self.repo.create_commit(
            ref_name, sig, sig, message, tree_oid, parent_oids
        )
        sha = str(commit_oid)
        gem.id = sha
        gem.parents = [str(p) for p in parent_oids]

        # One pending success note covering every bound test (single write).
        ts = gem.provenance.timestamp or time.time()
        if gem.tests():
            text = None
            for t in gem.tests():
                text = append_line(text, success_pending_event(t.id, ts))
            self._write_note(sha, SUCCESS_REF, text, sig)

        capture_ms = (time.perf_counter() - t0) * 1000.0
        return CaptureResult(sha=sha, branch=branch, capture_ms=capture_ms)

    def _build_tree(self, gem: Gem) -> pygit2.Oid:
        files = gem.to_files()  # {"gem/<name>": bytes}
        sub = self.repo.TreeBuilder()
        for path, data in files.items():
            name = path.split("/", 1)[1]
            blob = self.repo.create_blob(data)
            sub.insert(name, blob, pygit2.GIT_FILEMODE_BLOB)
        sub_oid = sub.write()
        root = self.repo.TreeBuilder()
        root.insert("gem", sub_oid, pygit2.GIT_FILEMODE_TREE)
        return root.write()

    def _signature(self, gem: Optional[Gem] = None) -> pygit2.Signature:
        if gem is not None:
            actor = gem.provenance.actor or self._actor
            ts = int(gem.provenance.timestamp or time.time())
        else:
            actor, ts = self._actor, int(time.time())
        return pygit2.Signature(actor, self._email, ts, 0)

    # ------------------------------------------------------------------ #
    # Valuation writes (notes; append-only — Invariant 1)
    # ------------------------------------------------------------------ #
    def attach_success(self, sha: str, test_id: str, score: float,
                       *, source: Optional[str] = None) -> None:
        ts = time.time()
        ev = success_score_event(test_id, score, ts, source=source)
        cur = self._read_note(sha, SUCCESS_REF)
        self._write_note(sha, SUCCESS_REF, append_line(cur, ev), self._signature())

    def attach_credit(self, sha: str, delta: float, source_sha: Optional[str] = None,
                      *, test: Optional[str] = None) -> None:
        ts = time.time()
        ev = credit_event(delta, ts, source=source_sha, test=test)
        cur = self._read_note(sha, CREDIT_REF)
        self._write_note(sha, CREDIT_REF, append_line(cur, ev), self._signature())

    def add_dependency_edge(self, consumer_sha: str, consumed_sha: str,
                            role: str = "consumed") -> None:
        """Record a *late-discovered* dependency edge (spec §4).

        Capture-time edges live in ``meta.json:consumed[]``; edges found after
        the fact append to the ``refs/notes/deps`` sidecar so the edge set is
        also immutable-append and auditable.
        """
        ts = time.time()
        ev = dep_event(consumed_sha, role, ts)
        cur = self._read_note(consumer_sha, DEPS_REF)
        self._write_note(consumer_sha, DEPS_REF, append_line(cur, ev), self._signature())

    # ------------------------------------------------------------------ #
    # Branch / selection ops (spec §1.7, §4)
    # ------------------------------------------------------------------ #
    def branch_frontier(self, task: str, *, base: str = MAIN) -> str:
        """Create the next ``frontier/<task>/<n>`` branch off ``base``."""
        n = self._next_frontier_index(task)
        name = f"frontier/{task}/{n}"
        base_tip = self._ref_target(f"refs/heads/{base}")
        if base_tip is not None:
            self.repo.references.create(f"refs/heads/{name}", base_tip)
        # If base is unborn, the branch is created lazily on first capture.
        return name

    def select_to_main(self, sha: str, *, actor: Optional[str] = None) -> str:
        """Cherry-pick a winning gem onto ``main`` (selection over merge, §1.7).

        Re-commits the gem's record tree onto main's tip, recording provenance
        (``Gem-Selected-From``).  Immutability preserved: the original frontier
        gem is untouched.
        """
        commit = self.repo.get(pygit2.Oid(hex=sha))
        tip = self._ref_target(f"refs/heads/{MAIN}")
        parents = [tip] if tip is not None else []
        sig = pygit2.Signature(actor or self._actor, self._email, int(time.time()), 0)
        msg = (commit.message.rstrip() + f"\n\nGem-Selected-From: {sha}\n")
        new_oid = self.repo.create_commit(
            f"refs/heads/{MAIN}", sig, sig, msg, commit.tree_id, parents
        )
        return str(new_oid)

    def tag_outcome(self, sha: str, test: str, ok: bool) -> str:
        """Tag an outcome: ``ok/<test>/<shortsha>`` or ``fail/<test>/<shortsha>``."""
        kind = "ok" if ok else "fail"
        safe_test = _sanitize_ref_component(test)
        name = f"refs/tags/{kind}/{safe_test}/{sha[:12]}"
        self.repo.references.create(name, pygit2.Oid(hex=sha), force=True)
        return name

    # ------------------------------------------------------------------ #
    # Reads / query primitives (used by index + browse)
    # ------------------------------------------------------------------ #
    def read_gem(self, sha: str) -> Gem:
        commit = self.repo.get(pygit2.Oid(hex=sha))
        if commit is None:
            raise KeyError(f"no such gem {sha}")
        files = self._read_gem_files(commit)
        parents = [str(p) for p in commit.parent_ids]
        gem = Gem.from_files(files, sha=sha, parents=parents)
        # Merge late-discovered dependency edges from the sidecar note.
        for ev in fold_deps(self._read_note(sha, DEPS_REF)):
            c = ev.get("consumed")
            if c and c not in gem.consumed:
                gem.consumed.append(c)
        return gem

    def _read_gem_files(self, commit: pygit2.Commit) -> dict[str, bytes]:
        tree = commit.tree
        if "gem" in tree:
            sub = self.repo.get(tree["gem"].id)
        else:  # tolerate flat layout
            sub = tree
        out: dict[str, bytes] = {}
        for name in GEM_FILES:
            if name in sub:
                blob = self.repo.get(sub[name].id)
                out[f"gem/{name}"] = blob.data
        return out

    def checkout(self, sha: str) -> tuple[Gem, list[str]]:
        """Epistemic rewind (Invariant 8): return the gem + its ancestry shas.

        Restores the agent's belief state as *data* (not a working directory):
        the gem at ``sha`` plus the chain of ancestor gem shas (the reasoning
        path that produced it).
        """
        gem = self.read_gem(sha)
        ancestry: list[str] = []
        commit = self.repo.get(pygit2.Oid(hex=sha))
        for c in self.repo.walk(commit.id, pygit2.GIT_SORT_TOPOLOGICAL):
            ancestry.append(str(c.id))
        return gem, ancestry

    def notes(self, sha: str) -> dict:
        """Folded valuation view for a gem: success map + credit summary."""
        succ = success_summary(self._read_note(sha, SUCCESS_REF))
        cred = fold_credit(self._read_note(sha, CREDIT_REF))
        return {
            "success": succ,
            "credit": {"total": cred.total, "n_events": cred.n_events,
                       "by_source": cred.by_source},
        }

    # -- subprocess-backed query primitives ----------------------------- #
    # All gem commits live under refs/heads + refs/tags; refs/notes/* (valuation)
    # is deliberately excluded from gem-space walks so notes-commits never leak
    # into retrieval or the parity count.
    _GEM_REFS = ("--branches", "--tags")

    def grep(self, pattern: str, *, all_refs: bool = True) -> list[str]:
        """Keyword retrieval over commit messages (``git log --grep``)."""
        args = ["log", "--format=%H", "-i", f"--grep={pattern}"]
        if all_refs:
            args += self._GEM_REFS
        return self._git_lines(args)

    def pickaxe(self, needle: str, *, regex: bool = False,
                all_refs: bool = True) -> list[str]:
        """Content/effect retrieval over diffs (``git log -S/-G``)."""
        flag = "-G" if regex else "-S"
        args = ["log", "--format=%H", flag, needle]
        if all_refs:
            args += self._GEM_REFS
        return self._git_lines(args)

    def by_tag(self, glob: str) -> list[str]:
        """Outcome filter (``git tag -l 'ok/*'``)."""
        return self._git_lines(["tag", "-l", glob])

    def frontier(self, task: str) -> dict[str, list[str]]:
        """Frontier query: gems on each ``frontier/<task>/*`` not yet on main."""
        out: dict[str, list[str]] = {}
        for ref in self.list_branches(prefix=f"frontier/{task}/"):
            out[ref] = self._git_lines(["log", "--format=%H", f"{MAIN}..{ref}"])
        return out

    def diff(self, sha_a: str, sha_b: str, path: Optional[str] = None) -> str:
        args = ["diff", sha_a, sha_b]
        if path:
            args += ["--", path]
        return self._git(args)

    # ------------------------------------------------------------------ #
    # Iteration (used by index.rebuild — parity assertion, spec §5)
    # ------------------------------------------------------------------ #
    def all_shas(self) -> list[str]:
        # Gem commits only — excludes refs/notes/* (valuation), so this count
        # is the parity reference for index.rebuild() (Invariant 6).
        return self._git_lines(["log", *self._GEM_REFS, "--format=%H"])

    def iter_gems(self) -> Iterable[Gem]:
        for sha in self.all_shas():
            yield self.read_gem(sha)

    def count_commits(self) -> int:
        return len(self.all_shas())

    def reachable_shas(self, refs: Sequence[str]) -> set[str]:
        """Set of gem shas reachable from the given refs (for §6.2 membrane).

        Sealed permeability restricts browse to ``main`` ∪ the agent's own
        branch; open permeability passes no restriction.
        """
        existing = [r for r in refs if self._ref_target(f"refs/heads/{r}") is not None]
        if not existing:
            return set()
        return set(self._git_lines(["log", "--format=%H", *existing]))

    def iter_outcome_tags(self):
        """Yield ``(kind, test, sha)`` for every ``ok/*`` / ``fail/*`` tag.

        Used by the index to expose an outcome filter (spec §5).  Resolves each
        tag ref to the full commit sha (the name carries only a short sha).
        """
        for ref_name in list(self.repo.references):
            if not (ref_name.startswith("refs/tags/ok/")
                    or ref_name.startswith("refs/tags/fail/")):
                continue
            ref = self.repo.references.get(ref_name)
            obj = self.repo.get(ref.target)
            sha = str(getattr(obj, "id", ref.target))
            parts = ref_name.split("/")  # refs tags <kind> <test> <short>
            kind = parts[2]
            test = parts[3] if len(parts) > 4 else ""
            yield kind, test, sha

    def list_branches(self, prefix: str = "") -> list[str]:
        out = []
        for name in self.repo.branches.local:
            if name.startswith(prefix):
                out.append(name)
        return sorted(out)

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _ref_target(self, ref_name: str) -> Optional[pygit2.Oid]:
        try:
            ref = self.repo.references.get(ref_name)
        except Exception:
            ref = None
        return ref.target if ref is not None else None

    def _next_frontier_index(self, task: str) -> int:
        existing = self.list_branches(prefix=f"frontier/{task}/")
        idxs = []
        for name in existing:
            tail = name.rsplit("/", 1)[-1]
            if tail.isdigit():
                idxs.append(int(tail))
        return (max(idxs) + 1) if idxs else 0

    # -- notes via pygit2 (fast, in-process) ---------------------------- #
    def _read_note(self, sha: str, ref: str) -> Optional[str]:
        try:
            note = self.repo.lookup_note(sha, ref)
        except (KeyError, pygit2.GitError):
            return None
        return note.message

    def _write_note(self, sha: str, ref: str, text: str,
                    sig: pygit2.Signature) -> None:
        self.repo.create_note(text, sig, sig, sha, ref, True)

    # -- subprocess git ------------------------------------------------- #
    def _git(self, args: list[str]) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.path), *args],
            capture_output=True, text=True, check=False,
        )
        return proc.stdout

    def _git_lines(self, args: list[str]) -> list[str]:
        return [ln for ln in self._git(args).splitlines() if ln.strip()]


# --------------------------------------------------------------------------- #
# Commit message (spec §4 — greppable body, machine-readable trailers)
# --------------------------------------------------------------------------- #
def _commit_message(gem: Gem) -> str:
    action = gem.action()
    action_name = action.name if action else gem.kind.value
    summary = f"{gem.kind.value}: {action_name}"
    reasoning = gem.reasoning_text().strip()
    abstract = reasoning.splitlines()[0] if reasoning else ""

    pre_tokens = " ".join(gem.index_keys.precondition_shape)
    test_ids = ",".join(t.id for t in gem.tests())
    consumed = ",".join(gem.consumed)

    trailers = [
        f"Gem-Kind: {gem.kind.value}",
        f"Gem-Action: {gem.index_keys.action_type or action_name}",
        f"Gem-Pre: {pre_tokens}",
        f"Gem-Tests: {test_ids}",
        f"Gem-Consumed: {consumed}",
        f"Gem-Reversibility: {gem.reversibility_class.value}",
    ]
    if gem.incited_by:
        trailers.append(f"Gem-Incited-By: {gem.incited_by}")

    parts = [summary]
    if abstract:
        parts.append(abstract)
    parts.append("\n".join(trailers))
    return "\n\n".join(parts) + "\n"


def _sanitize_ref_component(s: str) -> str:
    out = []
    for ch in s:
        out.append(ch if (ch.isalnum() or ch in "-_.") else "-")
    return "".join(out) or "x"
