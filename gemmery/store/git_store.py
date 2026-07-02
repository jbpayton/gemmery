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
                parents: Optional[list[str]] = None,
                path: Optional[str] = None) -> CaptureResult:
        """Write a gem into the ACCUMULATING memory filesystem + a pending note.

        The commit's tree is the parent's tree **plus** this gem's five files
        inserted at ``path`` — so every commit's tree is the *whole memory state*
        at that moment (spec §2.1: post-state IS the tree; the gem's effect IS
        ``git diff parent self``). ``git checkout <sha>`` therefore materializes
        the full store as a browsable file system as of that commit.

        ``path`` is the gem's home in that file system (e.g. ``knowledge/tells/P2``
        or ``decisions/round1``). Default: ``<kind>/<timestamp-ms>-<action>``.
        The path is recorded as a ``Gem-Path`` trailer so the commit's own gem is
        always recoverable. Returns a :class:`CaptureResult` with the measured
        capture time (< 25 ms invariant).
        """
        t0 = time.perf_counter()
        ref_name = f"refs/heads/{branch}"

        # Resolve parents: explicit > branch tip > orphan.
        if parents is None:
            tip = self._ref_target(ref_name)
            parent_oids = [tip] if tip is not None else []
        else:
            parent_oids = [pygit2.Oid(hex=p) for p in parents]

        base_tree = None
        if parent_oids:
            base_tree = self.repo.get(parent_oids[0]).tree

        if path is None:
            action = gem.action()
            stamp = int((gem.provenance.timestamp or time.time()) * 1000)
            path = f"{gem.kind.value}/{stamp}-{_sanitize_ref_component(action.name if action else gem.kind.value)}"
        parts = [_sanitize_path_component(p) for p in path.split("/") if p]
        parts = self._uniquify(base_tree, parts)
        path = "/".join(parts)

        gem_tree = self._gem_files_tree(gem)
        tree_oid = self._insert_subtree(base_tree, parts, gem_tree)
        sig = self._signature(gem)
        message = _commit_message(gem, path)

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

    def _gem_files_tree(self, gem: Gem) -> pygit2.Oid:
        files = gem.to_files()  # {"gem/<name>": bytes}
        sub = self.repo.TreeBuilder()
        for p, data in files.items():
            name = p.split("/", 1)[1]
            blob = self.repo.create_blob(data)
            sub.insert(name, blob, pygit2.GIT_FILEMODE_BLOB)
        return sub.write()

    def _insert_subtree(self, base_tree, parts: list[str],
                        sub_oid: pygit2.Oid) -> pygit2.Oid:
        """New tree = ``base_tree`` with ``sub_oid`` inserted at ``parts``."""
        tb = self.repo.TreeBuilder(base_tree) if base_tree is not None \
            else self.repo.TreeBuilder()
        name = parts[0]
        if len(parts) == 1:
            tb.insert(name, sub_oid, pygit2.GIT_FILEMODE_TREE)
        else:
            child = None
            if base_tree is not None and name in base_tree:
                entry = base_tree[name]
                if entry.filemode == pygit2.GIT_FILEMODE_TREE:
                    child = self.repo.get(entry.id)
            tb.insert(name, self._insert_subtree(child, parts[1:], sub_oid),
                      pygit2.GIT_FILEMODE_TREE)
        return tb.write()

    def _uniquify(self, base_tree, parts: list[str]) -> list[str]:
        """Never silently shadow an existing gem: suffix the leaf if taken."""
        tree = base_tree
        for name in parts[:-1]:
            if tree is None or name not in tree:
                return parts  # fresh directory -> leaf can't collide
            entry = tree[name]
            if entry.filemode != pygit2.GIT_FILEMODE_TREE:
                return parts
            tree = self.repo.get(entry.id)
        if tree is None or parts[-1] not in tree:
            return parts
        n = 2
        while f"{parts[-1]}-{n}" in tree:
            n += 1
        return parts[:-1] + [f"{parts[-1]}-{n}"]

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

        Inserts *only the winner's gem subtree* into main's current memory tree
        (never the frontier's whole state), recording ``Gem-Selected-From``.
        Immutability preserved: the original frontier gem is untouched.
        """
        commit = self.repo.get(pygit2.Oid(hex=sha))
        gem_path = _gem_path_from_message(commit.message) or "gem"
        parts = gem_path.split("/")
        sub = commit.tree
        for name in parts:
            sub = self.repo.get(sub[name].id)

        tip = self._ref_target(f"refs/heads/{MAIN}")
        parents = [tip] if tip is not None else []
        base_tree = self.repo.get(tip).tree if tip is not None else None
        parts = self._uniquify(base_tree, parts)
        new_tree = self._insert_subtree(base_tree, parts, sub.id)

        sig = pygit2.Signature(actor or self._actor, self._email, int(time.time()), 0)
        new_path = "/".join(parts)
        msg = _replace_gem_path(commit.message.rstrip(), new_path)
        msg += f"\n\nGem-Selected-From: {sha}\n"
        new_oid = self.repo.create_commit(
            f"refs/heads/{MAIN}", sig, sig, msg, new_tree, parents
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
        """Read THIS commit's gem via its ``Gem-Path`` trailer (legacy: ``gem/``)."""
        tree = commit.tree
        gem_path = _gem_path_from_message(commit.message)
        sub = tree
        if gem_path:
            for name in gem_path.split("/"):
                if name not in sub:
                    sub = None
                    break
                sub = self.repo.get(sub[name].id)
        if sub is None or gem_path is None:
            sub = self.repo.get(tree["gem"].id) if "gem" in tree else tree
        out: dict[str, bytes] = {}
        for name in GEM_FILES:
            if name in sub:
                blob = self.repo.get(sub[name].id)
                out[f"gem/{name}"] = blob.data
        return out

    def checkout(self, sha: str) -> tuple[Gem, list[str]]:
        """Epistemic rewind (Invariant 8): return the gem + its ancestry shas.

        The commit's tree IS the whole memory file system at that moment, so a
        literal ``git checkout <sha>`` (or :meth:`tree_listing`) reconstructs
        the full store as of this decision — not just this gem.
        """
        gem = self.read_gem(sha)
        ancestry: list[str] = []
        commit = self.repo.get(pygit2.Oid(hex=sha))
        for c in self.repo.walk(commit.id, pygit2.GIT_SORT_TOPOLOGICAL):
            ancestry.append(str(c.id))
        return gem, ancestry

    # ------------------------------------------------------------------ #
    # File-system view (the commit tree IS the memory state)
    # ------------------------------------------------------------------ #
    def _tree_at(self, sha: Optional[str] = None) -> pygit2.Tree:
        if sha is None:
            sha = str(self._ref_target(f"refs/heads/{MAIN}"))
        return self.repo.get(pygit2.Oid(hex=sha)).tree

    def ls(self, path: str = "", *, sha: Optional[str] = None) -> list[str]:
        """List the memory file system at ``path`` as of commit ``sha``."""
        tree = self._tree_at(sha)
        for name in [p for p in path.split("/") if p]:
            if name not in tree:
                return []
            tree = self.repo.get(tree[name].id)
        return sorted(e.name + ("/" if e.filemode == pygit2.GIT_FILEMODE_TREE else "")
                      for e in tree)

    def read_file(self, path: str, *, sha: Optional[str] = None) -> bytes:
        tree = self._tree_at(sha)
        parts = [p for p in path.split("/") if p]
        for name in parts[:-1]:
            tree = self.repo.get(tree[name].id)
        return self.repo.get(tree[parts[-1]].id).data

    def tree_listing(self, *, sha: Optional[str] = None,
                     dirs_only: bool = False) -> str:
        """An ``ls -R``-style listing of the memory as of ``sha``."""
        lines: list[str] = []

        def walk(tree, prefix):
            for e in sorted(tree, key=lambda x: x.name):
                if e.filemode == pygit2.GIT_FILEMODE_TREE:
                    lines.append(f"{prefix}{e.name}/")
                    walk(self.repo.get(e.id), prefix + "  ")
                elif not dirs_only:
                    lines.append(f"{prefix}{e.name}")

        walk(self._tree_at(sha), "")
        return "\n".join(lines)

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
def _commit_message(gem: Gem, path: Optional[str] = None) -> str:
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
    if path:
        trailers.append(f"Gem-Path: {path}")
    if gem.incited_by:
        trailers.append(f"Gem-Incited-By: {gem.incited_by}")

    parts = [summary]
    if abstract:
        parts.append(abstract)
    parts.append("\n".join(trailers))
    return "\n\n".join(parts) + "\n"


def _gem_path_from_message(message: str) -> Optional[str]:
    path = None
    for line in message.splitlines():
        if line.startswith("Gem-Path: "):
            path = line[len("Gem-Path: "):].strip()
    return path


def _replace_gem_path(message: str, new_path: str) -> str:
    lines = message.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Gem-Path: "):
            lines[i] = f"Gem-Path: {new_path}"
            return "\n".join(lines)
    return message + f"\nGem-Path: {new_path}"


def _sanitize_ref_component(s: str) -> str:
    out = []
    for ch in s:
        out.append(ch if (ch.isalnum() or ch in "-_.") else "-")
    return "".join(out) or "x"


def _sanitize_path_component(s: str) -> str:
    out = []
    for ch in s:
        out.append(ch if (ch.isalnum() or ch in "-_.") else "-")
    r = "".join(out).strip(".") or "x"
    return r
