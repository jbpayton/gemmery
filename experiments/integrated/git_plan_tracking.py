"""The 'hypotheses tracked by git' piece, concretely.

For one decision, each candidate plan ("rely on advisor A_i") is captured as a
gem on its own `frontier/plan/*` branch — the DAG literally holding the simulated
hypotheses. The chosen plan (argmax of the git-served model) is cherry-picked to
`main`. After the outcome, credit is attached as a note. This is the DAG-as-
search-tree: frontier = hypotheses, main = the selected plan, notes = backed-up
value.
"""
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from integrated_demo import run  # noqa: E402

from gemmery import (Action, Cost, DecisionBody, Gem, GitStore, IndexKeys,  # noqa: E402
                     Kind, Provenance, TestSpec)


def plan_gem(advisor, est_value):
    return Gem(
        kind=Kind.decision,
        provenance=Provenance(actor="planner", session_id="plan"),
        body=DecisionBody(
            action=Action("rely_on_advisor", {"advisor": advisor}),
            reasoning=f"Hypothesis: rely on {advisor}. Simulated value from git "
                      f"memory (current recency-filtered reliability) = {est_value:.3f}.",
            tests=[TestSpec("plan_success", "execute plan", "T-step reliance succeeds")],
            pre={"advisor": advisor}),
        cost=Cost(tokens=0),
        index_keys=IndexKeys(precondition_shape=["plan", advisor],
                             action_type="rely_on_advisor", domain=[advisor],
                             test_ids=["plan_success"]))


def main():
    prof, current, gm, mm, _ = run()
    store = GitStore(Path(tempfile.mkdtemp()) / "plans")

    # one seed gem on main so frontier branches have a base
    store.capture(Gem(kind=Kind.knowledge,
                      provenance=Provenance("planner", "plan"),
                      body=__import__("gemmery").KnowledgeBody(
                          action=Action("open_decision", {}),
                          reasoning="Decision point: choose an advisor to rely on."),
                      index_keys=IndexKeys(action_type="decision_point")))

    # capture each candidate plan as a HYPOTHESIS on its own frontier branch
    shas = {}
    for a in sorted(gm, key=lambda x: -gm[x]):
        br = store.branch_frontier(f"plan/{a}")
        shas[a] = store.capture(plan_gem(a, gm[a]), branch=br).sha
    print("hypotheses tracked in git (each a frontier branch):")
    for a in sorted(gm, key=lambda x: -gm[x]):
        print(f"  frontier/plan/{a}/0  -> rely on {a}  (simulated value {gm[a]:.3f})")

    # SELECT the best hypothesis to main (cherry-pick the winner)
    best = max(gm, key=gm.get)
    sel = store.select_to_main(shas[best])
    print(f"\nselected to main: rely on {best}  (git-served best current reliability)")

    # execute -> outcome -> back up credit as a note on the selected plan
    rng = random.Random(0)
    T = 6
    success = all(rng.random() < current[best] for _ in range(T))
    store.attach_success(sel, "plan_success", 1.0 if success else -1.0, source="outcome")
    store.attach_credit(sel, current[best] ** T, source_sha=shas[best], test="plan_success")
    print(f"executed {T}-step plan -> {'success' if success else 'failure'}; "
          f"credit note on main gem: {store.notes(sel)['credit']['total']:.3f}")

    # what the DAG looks like
    print("\nDAG summary:")
    print(f"  branches: {['main'] + store.list_branches(prefix='frontier/plan')}")
    print(f"  main tip carries the chosen plan; frontier/* retain the alternatives "
          f"for later synthesis; success + credit live in notes (immutable record, "
          f"mutable valuation).")


if __name__ == "__main__":
    main()
