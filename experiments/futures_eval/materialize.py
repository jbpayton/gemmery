"""Materialize the A/B's explored futures as REAL git branches.

One store; per scenario S<k>:
  * main: decision/S<k>/situation (belief + day-1 statements)
  * frontier/s<k>/vote-<v>: a plan gem + a rollout gem per candidate vote —
    the same simulate() output the branch-arm prompt carries (verified below,
    so the prompt is provably derived from store content).
After the arms answer, record.py writes each arm's pick back as a decision gem
consuming the rollout it chose, selects the branch-arm's winner to main, and
credits every explored future by its EV gap (opportunity cost).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from build_eval import PLAYERS, simulate, transcript, gen_scenario, mine  # noqa: E402

from gemmery import (Action, DecisionBody, Gem, GitStore, IndexKeys,  # noqa: E402
                     KnowledgeBody, Kind, Provenance, TestSpec)

TS = 1_700_400_000


def main():
    if (ROOT / "store").exists():
        shutil.rmtree(ROOT / "store")
    store = GitStore(ROOT / "store", actor="focal-P0")
    traps, controls = mine()
    scenarios = traps + controls
    branch_prompt = (ROOT / "prompt_branch.txt").read_text()

    tips = {}
    for k, (seed, belief, accusers, evs, myopic, best, gap) in enumerate(scenarios):
        sid = f"S{k}"
        sit = Gem(kind=Kind.knowledge,
                  provenance=Provenance("focal-P0", "eval", timestamp=TS + k),
                  body=KnowledgeBody(
                      action=Action("frame_decision", {"scenario": sid}),
                      reasoning=(f"Scenario {sid}. Day-1 statements:\n"
                                 f"{transcript(accusers)}\nBelief: {json.dumps(belief)}"),
                      belief="pre-fork state"),
                  index_keys=IndexKeys(action_type="decision_point", domain=[sid]))
        store.capture(sit, path=f"decision/{sid}/situation")

        for v in PLAYERS:
            br = store.branch_frontier(f"s{k}/vote-{v}")
            plan = Gem(kind=Kind.decision,
                       provenance=Provenance("focal-P0", "eval", timestamp=TS + 100 + k),
                       body=DecisionBody(
                           action=Action("vote", {"target": v, "scenario": sid}),
                           reasoning=f"IN THIS FUTURE ({sid}) we vote {v}.",
                           tests=[TestSpec("ev_vs_optimal", "score pick", "EV gap")],
                           pre={"vote": v}),
                       index_keys=IndexKeys(action_type="vote", domain=[sid, v]))
            store.capture(plan, branch=br, path=f"futures/{sid}/vote-{v}/plan")
            timelines = []
            for w in PLAYERS:
                _, tl = simulate(v, w, belief, accusers)
                line = f"- if wolf is {w} (P={belief[w]:.2f}): {tl}"
                timelines.append(line)
                # the branch-arm prompt must be derivable from this store content
                assert tl in branch_prompt, (sid, v, w)
            roll = Gem(kind=Kind.knowledge,
                       provenance=Provenance("focal-P0", "eval", timestamp=TS + 200 + k),
                       body=KnowledgeBody(
                           action=Action("simulate_future", {"vote": v, "scenario": sid}),
                           reasoning=(f"SIMULATED CONSEQUENCES ({sid}, vote {v}); "
                                      f"true EV {evs[v]:.3f}\n" + "\n".join(timelines)),
                           belief=f"future {sid}/vote-{v}"),
                       index_keys=IndexKeys(action_type="rollout", domain=[sid, v]))
            r = store.capture(roll, branch=br, path=f"futures/{sid}/vote-{v}/rollout")
            tips[f"{sid}/{v}"] = r.sha

    json.dump(tips, open(ROOT / "tips.json", "w"), indent=1)
    print(f"materialized {len(scenarios)} scenarios x {len(PLAYERS)} futures = "
          f"{len(tips)} branches; store gems: {store.count_commits()}")
    print("every rollout line verified present in the branch-arm prompt "
          "(prompt is derived from store content)")


if __name__ == "__main__":
    main()
