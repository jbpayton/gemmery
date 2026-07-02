"""Phase 2: capture each branch's self-assessment as a gem ON that branch,
diff the futures against each other, select the winner to main, execute the
real outcome, credit — and emit the counterfactual-explainer prompt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from gemmery import (Action, Gem, GitStore, IndexKeys, KnowledgeBody, Kind,  # noqa: E402
                     Provenance)

PLAYERS = ["P1", "P2", "P3", "P4"]
TS = 1_700_300_100
F = json.load(open(ROOT / "futures.json"))
store = GitStore(ROOT / "store")


def load(v):
    t = (ROOT / "out" / f"vote-{v}.json").read_text().strip()
    if "```" in t:
        t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)


assess, tips = {}, {}
for i, v in enumerate(PLAYERS):
    a = load(v)
    assess[v] = a
    gem = Gem(kind=Kind.knowledge,
              provenance=Provenance("branch-explorer", "futures", timestamp=TS + i),
              body=KnowledgeBody(
                  action=Action("assess_future", {"vote": v}),
                  reasoning=(f"Stance: {a['stance']} (confidence {a['confidence_0_1']}).\n"
                             f"Why we would: {a['why_we_would']}\n"
                             f"Risks: {a['risks']}"),
                  belief=f"assessment of vote-{v} future"),
              consumed=[F["tips"][v]],
              index_keys=IndexKeys(action_type="assessment", domain=[v]))
    r = store.capture(gem, branch=F["branches"][v], path=f"futures/vote-{v}/assessment")
    tips[v] = r.sha

# ---- diff between the top-2 futures: the computed marginal consequence ----
ranked = sorted(PLAYERS, key=lambda v: -F["ev"][v])
best, runner = ranked[0], ranked[1]
diff = store.diff(tips[runner], tips[best], path=None)
(ROOT / "diff_top2.txt").write_text(diff)

# ---- select the winner to main; execute the REAL outcome ----
sel = store.select_to_main(tips[best])  # brings the winning future's assessment
plan_sha = store.history(f"futures/vote-{best}/plan", branch=F["branches"][best])[0]
sel_plan = store.select_to_main(plan_sha)
wolf = F["wolf"]
won = best == wolf
store.tag_outcome(sel_plan, "game_outcome", ok=won)
store.attach_success(sel_plan, "game_outcome", 1.0 if won else -1.0, source="reveal")
for v in PLAYERS:  # value the roads not taken too: EV gap vs chosen, as credit
    store.attach_credit(tips[v], round(F["ev"][v] - F["ev"][best], 3),
                        source_sha=sel_plan, test="game_outcome")

# ---- the trace for the counterfactual explainer (from git only) ----
lines = [f"Decision: P0's Day-1 vote. Belief: {json.dumps(F['belief'])}.",
         f"Reveal (after execution): the wolf was {wolf}. "
         f"Chosen future: vote-{best} -> {'WIN day 1' if won else 'wrong'}.\n"]
for v in ranked:
    a = assess[v]
    roll = store.read_file(f"futures/vote-{v}/rollout/reasoning.md",
                           sha=F["tips"][v]).decode()
    ev_line = roll.splitlines()[1]
    lines.append(f"--- branch frontier/future/vote-{v} ---")
    lines.append(ev_line)
    lines.append(f"inhabitant stance: {a['stance']} ({a['confidence_0_1']})")
    lines.append(f"why we would: {a['why_we_would']}")
    lines.append(f"risks: {a['risks']}")
    lines.append(f"simulated timeline (most likely hypothesis):")
    seg = roll.split("IF the wolf is P2")[1].split("IF the wolf is")[0] if "IF the wolf is P2" in roll else ""
    lines.append("  IF the wolf is P2" + seg.rstrip())
    lines.append("")
trace = "\n".join(lines)
(ROOT / "trace.txt").write_text(trace)

(ROOT / "prompt_explainer.txt").write_text(
    "Below is the git record of a decision made by branching reality: one branch "
    "per candidate Day-1 vote in a Werewolf game, each with a simulated future, "
    "an inhabitant's case for it, and an expected value; the winner was executed. "
    "Write a concise POST-HOC COUNTERFACTUAL analysis (3 short paragraphs): "
    "(1) why we chose the path we chose; (2) why we WOULD have chosen vote-P1 "
    "had we taken it — and what its future held; (3) what the branch apparatus "
    "bought us that a single-path decision would not have.\n\n" + trace)

print(f"selected: vote-{best} (EV {F['ev'][best]:.3f}) -> "
      f"{'WON on day 1' if won else 'missed'}; runner-up vote-{runner}")
print("stances:", {v: assess[v]["stance"] for v in PLAYERS})
print("credit on roads not taken:", {v: round(F['ev'][v] - F['ev'][best], 3) for v in PLAYERS})
print("\n=== diff(top-2 futures) stat ===")
import subprocess
print(subprocess.run(["git", "-C", str(ROOT / "store"), "diff", "--stat",
                      tips[runner], tips[best]], capture_output=True, text=True).stdout)
