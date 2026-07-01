"""Materialize the good-case plan DAG in a real git store, show what's inside,
and show that git is a post-hoc EXPLAINER: the whole memory state is traversable
over time, so you can reconstruct *why* each hypothesis was made.

Writes:
  * example_repo/         a real Gemmery GitStore (gitignored)
  * WHATS_IN_GIT.md       a dump of the actual git contents + the explainer walk
  * git_dag.png           the structure (hypotheses -> selection -> notes)
  * git_timeline.png      an advisor's reliability trail over time (why trust drifted)

Deterministic (fixed timestamps) so the SHAs and the document are reproducible.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "example_repo"
sys.path.insert(0, str(ROOT))

from gemmery import (Action, Cost, DecisionBody, Gem, GitStore, IndexKeys,  # noqa: E402
                     KnowledgeBody, Kind, Provenance, TestSpec)

# candidate advisors: (name, current reliability, one-line note)
CANDIDATES = [
    ("A_now", 0.89, "currently the most reliable (recent record)"),
    ("A_good", 0.80, "solid, but a notch below"),
    ("A_fallen", 0.38, "great long ago, unreliable NOW"),
    ("A_noise", 0.33, "roughly a coin / misleading"),
]
# A_fallen's reliability trail over time -> shows WHY trust drifted, and why a
# stale read (flat file) would be fooled while git's recent query is not.
FALLEN_TRAIL = [(0.85, "1yr ago"), (0.55, "6mo ago"), (0.38, "now")]
TS = 1_700_000_000


def K(reasoning, action="observe", **ik):
    return Gem(kind=Kind.knowledge,
               provenance=Provenance("planner", "sess-2026-07-01", timestamp=TS),
               body=KnowledgeBody(action=Action(action, {}), reasoning=reasoning),
               index_keys=IndexKeys(**ik))


def build_store():
    if REPO.exists():
        shutil.rmtree(REPO)
    store = GitStore(REPO, actor="planner", email="planner@gemmery.local")

    # --- memory the planner will consult: one 'current reliability' evidence gem
    # per advisor, plus A_fallen's decline trail (traversable over time) ---
    ev = {}
    for i, (name, val, note) in enumerate(CANDIDATES):
        g = K(f"Evidence: recency-filtered reliability of {name} = {val:.2f} "
              f"(git query over the recent window). {note}.",
              action="recency_reliability", action_type="evidence",
              domain=[name], precondition_shape=["reliability", name])
        g.provenance.timestamp = TS + i
        ev[name] = store.capture(g, branch="main").sha

    fallen_trail = []
    for j, (val, when) in enumerate(FALLEN_TRAIL):
        g = K(f"Observation ({when}): A_fallen's reliability measured at {val:.2f}.",
              action="reliability_observation", action_type="evidence",
              domain=["A_fallen"], precondition_shape=["reliability", "A_fallen", when.replace(' ', '_')])
        g.provenance.timestamp = TS + 10 + j
        fallen_trail.append(store.capture(g, branch="main").sha)

    # --- decision point ---
    dp = K("Decision point: whom to rely on for a multi-step plan? Consult the "
           "current reliability evidence for each advisor.",
           action="open_decision", action_type="decision_point", domain=["plan"])
    dp.provenance.timestamp = TS + 20
    store.capture(dp, branch="main")

    # --- one HYPOTHESIS gem per candidate, each CONSUMING its evidence gem ---
    shas = {}
    for i, (name, val, note) in enumerate(CANDIDATES):
        br = store.branch_frontier(f"plan/{name}")
        g = Gem(kind=Kind.decision,
                provenance=Provenance("planner", "sess-2026-07-01", timestamp=TS + 30 + i),
                body=DecisionBody(
                    action=Action("rely_on_advisor", {"advisor": name}),
                    reasoning=f"Hypothesis: rely on {name}. Simulated plan value = its "
                              f"current reliability {val:.2f} (see consumed evidence). "
                              f"{note}.",
                    tests=[TestSpec("plan_success", "run T-step plan", "all steps hold")],
                    pre={"advisor": name, "sim_value": val}),
                cost=Cost(tokens=0),
                consumed=[ev[name]],                       # <- the 'why' edge
                index_keys=IndexKeys(precondition_shape=["plan", name],
                                     action_type="rely_on_advisor", domain=[name],
                                     test_ids=["plan_success"]))
        shas[name] = store.capture(g, branch=br).sha

    # --- SELECT the winner to main; tag + credit the outcome ---
    best = "A_now"
    sel = store.select_to_main(shas[best], actor="planner")
    store.add_dependency_edge(sel, ev[best], role="decisive_evidence")
    store.tag_outcome(sel, "plan_success", ok=True)
    store.attach_success(sel, "plan_success", 1.0, source="outcome")
    store.attach_credit(sel, round(0.89 ** 6, 3), source_sha=shas[best], test="plan_success")
    return store, ev, shas, best, sel, fallen_trail


def git(*a):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout.rstrip()


def dump_doc(store, ev, shas, best, sel, fallen_trail):
    log = git("log", "--graph", "--oneline", "--decorate", "--branches", "--tags", "--date-order")
    refs = git("for-each-ref", "--format=%(refname)")
    meta = git("show", "main:gem/meta.json")
    reasoning = git("show", "main:gem/reasoning.md")
    notes = store.notes(sel)
    sel_gem = store.read_gem(sel)
    # reconstruct the rationale from the DAG
    why_lines = []
    for name, val, _ in CANDIDATES:
        mark = "  <-- SELECTED" if name == best else ""
        why_lines.append(f"  rely_on({name}): value {val:.2f}{mark}")
    fallen_hist = "\n".join(
        f"    {git('show', f'{s}:gem/reasoning.md').strip()}" for s in fallen_trail)

    doc = f"""# What is actually in Git — the good case (with the post-hoc explainer)

A real Gemmery `GitStore` (regenerate with
`python experiments/integrated/show_whats_in_git.py`). It captures ONE planning
decision end to end, and — because every state is an immutable commit and
valuation is append-only — the whole thing is **traversable after the fact**.

## 1. The DAG

```
{log}
```

`main` = evidence gems the planner consulted, the decision point, and the
selected plan (cherry-picked). Each `frontier/plan/*` branch is one hypothesis.

## 2. Refs (branches, outcome tag, note refs)

```
{refs}
```

## 3. A gem on disk (`main:gem/meta.json`) — note `consumed`

```json
{meta}
```

`reasoning.md` (the *why*):

```
{reasoning}
```

## 4. Valuation notes on the selected gem (folded)

```json
{json.dumps(notes, indent=2)}
```

---

# Git as a post-hoc explainer

The question "why was this hypothesis made?" is answerable *entirely from the
repository*, after the fact:

**(a) Why was `rely_on({best})` chosen?** Walk the selected plan's `consumed`
edge → the evidence gem it rested on:

```
selected plan {sel[:10]}  --consumed-->  evidence {ev[best][:10]}
  "{git('show', ev[best] + ':gem/reasoning.md').strip()}"
```

and the alternatives are still on their `frontier/plan/*` branches, so you can
see *what else was considered and why it lost*:

```
{chr(10).join(why_lines)}
```

`{best}` had the highest simulated value → selected. Nothing was discarded; the
losing hypotheses remain, each with its own `consumed` evidence.

**(b) The whole memory state is traversable over time.** `A_fallen` was once
trustworthy and has decayed — and that history is walkable:

```
{fallen_hist}
```

The planner consumed the **recent** reliability (0.38), so it correctly
distrusted `A_fallen`. A flat notes file read from the top would have seen only
the stale 0.85 and been fooled — the failure mode from the integrated test. Here
you can *prove* which value the decision used (`git show
{sel[:10]}` and its consumed edge) and reconstruct the exact memory as of any
commit (`git checkout <sha>`; `git show <sha>:gem/...`).

**(c) Valuation history is preserved too.** Credit and success are append-only
notes, so `git log refs/notes/credit` replays how a belief's value evolved — you
can see not just *what* is believed now but *how it came to be*.

## Why a flat/overwritten store can't do this

A markdown scratchpad that is edited in place, or a vector index that is mutated,
keeps only the *current* state. Git keeps *every* state plus the dependency edges
and the append-only valuation, so the causal trace — what was known, what it
rested on, and why a choice looked best at the time — is fully recoverable. That
is auditability and post-hoc explanation as a property of the substrate, not an
add-on.
"""
    (ROOT / "WHATS_IN_GIT.md").write_text(doc)
    print("wrote", ROOT / "WHATS_IN_GIT.md")


def draw_diagram(best):
    fig, ax = plt.subplots(figsize=(13, 6.0)); ax.axis("off")

    def box(x, y, t, c, w=2.6, h=0.9, fs=8.2):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06", fc=c, ec="black", lw=1.2))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs)

    def arr(x1, y1, x2, y2, s="-", c="black"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=13, lw=1.4, color=c, ls=s))

    box(0.1, 4.35, "decision\npoint (main)", "#dfe7f5", w=2.1)
    ys = [6.5, 5.05, 3.6, 2.15]
    for (name, val, _), y in zip(CANDIDATES, ys):
        sel = name == best
        box(3.2, y, f"frontier/plan/{name}\nrely_on({name})  val {val:.2f}",
            "#bfe3bf" if sel else "#f0f0f0", w=3.0)
        arr(2.2, 4.8, 3.2, y + 0.45)
        box(6.9, y + 0.1, f"evidence:\n{name} = {val:.2f}", "#eee3f7", w=1.9, h=0.7, fs=7.8)
        arr(6.2, y + 0.45, 6.9, y + 0.45, s=":", c="#7b52ab")
    ax.text(6.15, 7.35, "consumed = the 'why'", fontsize=8, color="#7b52ab")
    box(9.6, 5.0, "selected plan\n(main, tagged ok)", "#9ecae1", w=2.8)
    arr(6.2, ys[0] + 0.45, 9.6, 5.45, s="--", c="#1f77b4")
    ax.text(7.3, 6.35, "cherry-pick\nwinner → main", fontsize=8, color="#1f77b4")
    box(9.5, 2.9, "notes (append-only):\nsuccess = +1.0\ncredit  = +0.50", "#fde9c8", w=3.0, h=1.1, fs=8)
    arr(11.0, 5.0, 11.0, 4.0, c="#d9822b")
    ax.text(11.15, 4.45, "valuation", fontsize=7.5, color="#d9822b", rotation=90, va="center")
    ax.set_xlim(0, 13); ax.set_ylim(1.7, 7.8)
    ax.set_title("What's in git (good case): each hypothesis is a frontier branch with a "
                 "'consumed' edge to the evidence it rests on (the why);\n"
                 "the winner is cherry-picked to main; commits are immutable, valuation is "
                 "append-only notes", fontsize=10.5)
    plt.tight_layout(); plt.savefig(ROOT / "git_dag.png", dpi=130); print("wrote", ROOT / "git_dag.png")


def draw_timeline():
    plt.figure(figsize=(7.6, 4.2))
    xs = list(range(len(FALLEN_TRAIL)))
    ys = [v for v, _ in FALLEN_TRAIL]
    plt.plot(xs, ys, "-o", lw=2.4, color="#d62728")
    for x, (v, when) in zip(xs, FALLEN_TRAIL):
        plt.annotate(f"{v:.2f}\n({when})", (x, v), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=9)
    plt.axhline(0.5, ls="--", c="gray", lw=1); plt.text(0, 0.52, "coin flip", fontsize=8, color="gray")
    plt.annotate("stale read (flat file) sees this\n→ over-trusts A_fallen", (0, 0.85),
                 xytext=(0.4, 0.7), fontsize=8, color="#7f7f7f",
                 arrowprops=dict(arrowstyle="->", color="#7f7f7f"))
    plt.annotate("git's recency query sees THIS\n→ correctly distrusts A_fallen", (2, 0.38),
                 xytext=(0.9, 0.30), fontsize=8, color="#1f77b4",
                 arrowprops=dict(arrowstyle="->", color="#1f77b4"))
    plt.ylim(0.2, 1.0); plt.xticks(xs, [w for _, w in FALLEN_TRAIL])
    plt.ylabel("A_fallen reliability"); plt.xlabel("time (every state kept in git → walkable)")
    plt.title("Traversable over time: an advisor's trust history is recoverable from git")
    plt.grid(alpha=0.25); plt.tight_layout()
    plt.savefig(ROOT / "git_timeline.png", dpi=130); print("wrote", ROOT / "git_timeline.png")


if __name__ == "__main__":
    store, ev, shas, best, sel, fallen_trail = build_store()
    dump_doc(store, ev, shas, best, sel, fallen_trail)
    draw_diagram(best)
    draw_timeline()
