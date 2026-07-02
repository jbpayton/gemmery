"""``gemmery`` command-line interface.

Thin dispatch over the library so capture/browse/eval are usable from a shell
(and so the skill's ``scripts/`` can wrap one engine rather than re-implementing
it).  Capture and browse are *intentional* actions (Invariant 5) — the agent
invokes them deliberately; nothing here runs as a background hook.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from .browse import BudgetMeter, MockPolicy, Permeability, browse, one_shot
from .index import GemIndex
from .model import (
    Action,
    Cost,
    DecisionBody,
    Gem,
    IndexKeys,
    KnowledgeBody,
    Kind,
    ObservationBody,
    Provenance,
    Reversibility,
    TestSpec,
)
from .store import GitStore

DEFAULT_STORE = ".gemmery-store"


def store_path() -> Path:
    return Path(os.environ.get("GEMMERY_STORE", DEFAULT_STORE))


def open_store() -> GitStore:
    return GitStore(store_path())


def open_index(store: GitStore, *, rebuild: bool = True) -> GemIndex:
    db = store_path() / "index.sqlite"
    idx = GemIndex(db_path=str(db))
    if rebuild:
        idx.rebuild(store)
    else:
        idx.load_vectors()
    return idx


# --------------------------------------------------------------------------- #
# Build a gem from a simple JSON spec (the capture contract)
# --------------------------------------------------------------------------- #
def gem_from_spec(spec: dict) -> Gem:
    kind = Kind(spec.get("kind", "decision"))
    prov = Provenance(actor=spec.get("actor", "agent"),
                      session_id=spec.get("session", "cli"))
    tests = [TestSpec(**t) if isinstance(t, dict) else TestSpec(id=str(t))
             for t in spec.get("tests", [])]
    action = Action(**spec["action"]) if isinstance(spec.get("action"), dict) \
        else Action(name=spec.get("action", kind.value))

    if kind is Kind.decision:
        body = DecisionBody(action=action, reasoning=spec.get("reasoning", ""),
                            tests=tests, pre=spec.get("pre", {}))
    elif kind is Kind.knowledge:
        body = KnowledgeBody(action=action, reasoning=spec.get("reasoning", ""),
                             belief=spec.get("belief", ""),
                             credence=spec.get("credence", 0.5),
                             tests=tests, pre=spec.get("pre", {}))
    else:
        body = ObservationBody(content=spec.get("content", ""),
                               reasoning=spec.get("reasoning", ""),
                               pre=spec.get("pre", {}))

    ik = IndexKeys(
        precondition_shape=spec.get("precondition_shape", []),
        action_type=spec.get("action_type", action.name),
        domain=spec.get("domain", []),
        test_ids=[t.id for t in tests],
    )
    return Gem(
        kind=kind, provenance=prov, body=body,
        cost=Cost(**spec.get("cost", {})),
        reversibility_class=Reversibility(spec.get("reversibility", "pure")),
        index_keys=ik,
        consumed=spec.get("consumed", []),
        incited_by=spec.get("incited_by"),
    )


# --------------------------------------------------------------------------- #
# Subcommands
# --------------------------------------------------------------------------- #
def cmd_capture(args) -> int:
    raw = Path(args.spec).read_text() if args.spec and args.spec != "-" \
        else sys.stdin.read()
    spec = json.loads(raw)
    store = open_store()
    path = args.path or spec.get("path")
    if getattr(args, "revise", False):
        if not path:
            print("revise requires --path (the stable home of the note)", file=sys.stderr)
            return 2
        res = store.revise(gem_from_spec(spec), path, branch=args.branch)
    else:
        res = store.capture(gem_from_spec(spec), branch=args.branch, path=path)
    print(json.dumps({"sha": res.sha, "branch": res.branch,
                      "path": store.gem_path(res.sha),
                      "capture_ms": round(res.capture_ms, 3)}))
    if res.capture_ms >= 25:
        print(f"warning: capture took {res.capture_ms:.1f}ms (>25ms invariant)",
              file=sys.stderr)
    return 0


def cmd_ls(args) -> int:
    store = open_store()
    if args.recursive:
        print(store.tree_listing(sha=args.sha))
    else:
        print("\n".join(store.ls(args.path or "", sha=args.sha)))
    return 0


def cmd_cat(args) -> int:
    store = open_store()
    sys.stdout.write(store.read_file(args.path, sha=args.sha).decode())
    return 0


def cmd_history(args) -> int:
    store = open_store()
    shas = store.history(args.path)
    for sha in shas:
        gem = store.read_gem(sha)
        first = gem.reasoning_text().strip().splitlines()
        print(f"{sha[:12]}  {first[0][:90] if first else ''}")
    if not shas:
        print(f"(no history at {args.path})")
    return 0


def cmd_browse(args) -> int:
    store = open_store()
    index = open_index(store)
    meter = BudgetMeter(max_calls=args.budget)
    res = browse(args.goal, store=store, index=index, policy=MockPolicy(),
                 budget=meter, top_k=args.top_k, max_iters=args.max_iters,
                 permeability=Permeability(args.permeability))
    out = {
        "mode": res.mode, "satisfied": res.satisfied,
        "iterations": res.iterations, "budget": res.budget,
        "marks": [{"sha": m.sha, "reason": m.reason,
                   "relevance": round(m.relevance, 3)} for m in res.marks[:args.top_k]],
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_oneshot(args) -> int:
    store = open_store()
    index = open_index(store)
    res = one_shot(args.goal, store=store, index=index, top_k=args.top_k)
    print(json.dumps([{"sha": m.sha, "relevance": round(m.relevance, 3)}
                      for m in res.marks], indent=2))
    return 0


def cmd_notes(args) -> int:
    print(json.dumps(open_store().notes(args.sha), indent=2))
    return 0


def cmd_success(args) -> int:
    open_store().attach_success(args.sha, args.test, args.score, source=args.source)
    print(f"attached success {args.score} for {args.test} on {args.sha[:12]}")
    return 0


def cmd_rebuild(args) -> int:
    store = open_store()
    idx = open_index(store)
    print(json.dumps({"commits": store.count_commits(), "indexed": idx.count()}))
    return 0


def cmd_decorrelation(args) -> int:
    from .eval import build_dataset, decorrelation_report
    rep = decorrelation_report(build_dataset())
    print(json.dumps({k: v for k, v in rep.to_dict().items() if k != "pairs"},
                     indent=2))
    return 0


def cmd_phase0(args) -> int:
    from .eval.run_phase0 import main as p0
    return p0(["--gain", str(args.gain), "--out", args.out,
               "--n-exploratory", str(args.n_exploratory),
               "--n-confirmatory", str(args.n_confirmatory)])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gemmery", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capture", help="capture a gem from a JSON spec (or stdin)")
    c.add_argument("spec", nargs="?", default="-")
    c.add_argument("--branch", default="main")
    c.add_argument("--path", help="the gem's home in the memory file system "
                                  "(e.g. knowledge/tells/P2)")
    c.add_argument("--revise", action="store_true",
                   help="replace the note at --path (new version at HEAD, "
                        "prior versions stay in history)")
    c.set_defaults(fn=cmd_capture)

    l = sub.add_parser("ls", help="list the memory file system")
    l.add_argument("path", nargs="?", default="")
    l.add_argument("-R", "--recursive", action="store_true")
    l.add_argument("--sha", help="view the memory as of this commit")
    l.set_defaults(fn=cmd_ls)

    ct = sub.add_parser("cat", help="print a memory file (e.g. .../reasoning.md)")
    ct.add_argument("path")
    ct.add_argument("--sha", help="view as of this commit")
    ct.set_defaults(fn=cmd_cat)

    hi = sub.add_parser("history", help="version history of a note at a path")
    hi.add_argument("path")
    hi.set_defaults(fn=cmd_history)

    b = sub.add_parser("browse", help="run the agentic browse loop")
    b.add_argument("goal")
    b.add_argument("--budget", type=int, default=8)
    b.add_argument("--top-k", type=int, default=8)
    b.add_argument("--max-iters", type=int, default=6)
    b.add_argument("--permeability", default="sealed", choices=["sealed", "open"])
    b.set_defaults(fn=cmd_browse)

    o = sub.add_parser("one-shot", help="single static top-k lookup (baseline)")
    o.add_argument("goal")
    o.add_argument("--top-k", type=int, default=8)
    o.set_defaults(fn=cmd_oneshot)

    n = sub.add_parser("notes", help="show folded valuation (success + credit)")
    n.add_argument("sha")
    n.set_defaults(fn=cmd_notes)

    s = sub.add_parser("success", help="attach a signed success score (note)")
    s.add_argument("sha"); s.add_argument("test")
    s.add_argument("score", type=float); s.add_argument("--source")
    s.set_defaults(fn=cmd_success)

    r = sub.add_parser("rebuild-index", help="rebuild the index from git; assert parity")
    r.set_defaults(fn=cmd_rebuild)

    d = sub.add_parser("decorrelation", help="Phase-0 §10.2 feasibility report")
    d.set_defaults(fn=cmd_decorrelation)

    z = sub.add_parser("phase0", help="run the Phase-0 kill-switch end to end")
    z.add_argument("--gain", type=float, default=0.5)
    z.add_argument("--out", default="phase0_artifacts")
    z.add_argument("--n-exploratory", type=int, default=40)
    z.add_argument("--n-confirmatory", type=int, default=98)
    z.set_defaults(fn=cmd_phase0)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
