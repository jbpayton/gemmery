"""Record the arms' picks back into the store: decision gems consuming the
chosen rollouts, branch-arm winners selected to main, every explored future
credited by its EV gap (opportunity cost)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from build_eval import PLAYERS  # noqa: E402

from gemmery import (Action, DecisionBody, Gem, GitStore, IndexKeys, Kind,  # noqa: E402
                     Provenance, TestSpec)

TS = 1_700_401_000
meta = json.load(open(ROOT / "meta.json"))
tips = json.load(open(ROOT / "tips.json"))
store = GitStore(ROOT / "store")


def load(arm):
    t = (ROOT / "out" / f"{arm}.json").read_text().strip()
    if "```" in t:
        t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)


picks = {a: load(a) for a in ("direct", "branch")}
n_sel = n_credit = 0
for k, sid in enumerate(sorted(meta, key=lambda s: int(s[1:]))):
    m = meta[sid]
    for arm in ("direct", "branch"):
        p = picks[arm][sid]
        gem = Gem(kind=Kind.decision,
                  provenance=Provenance(f"{arm}-arm", "eval", timestamp=TS + k),
                  body=DecisionBody(
                      action=Action("final_vote", {"scenario": sid, "vote": p, "arm": arm}),
                      reasoning=(f"{arm} arm votes {p} in {sid}. True EV "
                                 f"{m['evs'][p]:.3f} (optimal {m['evs'][m['best']]:.3f})."),
                      tests=[TestSpec("ev_vs_optimal", "compare", "gap 0")],
                      pre={"scenario": sid}),
                  consumed=[tips[f"{sid}/{p}"]],
                  index_keys=IndexKeys(action_type="final_vote", domain=[sid, arm]))
        sha = store.capture(gem, path=f"decision/{sid}/pick-{arm}").sha
        gap = m["evs"][p] - m["evs"][m["best"]]
        store.attach_success(sha, "ev_vs_optimal", 1.0 if gap == 0 else max(-1.0, gap * 5),
                             source="scoring")
        store.tag_outcome(sha, "ev_vs_optimal", ok=(gap == 0))
    # select the branch-arm's chosen future to main; credit ALL explored futures
    chosen = picks["branch"][sid]
    store.select_to_main(tips[f"{sid}/{chosen}"])
    n_sel += 1
    for v in PLAYERS:
        store.attach_credit(tips[f"{sid}/{v}"],
                            round(m["evs"][v] - m["evs"][m["best"]], 3),
                            source_sha=None, test="ev_vs_optimal")
        n_credit += 1

print(f"recorded {len(meta) * 2} pick gems, selected {n_sel} chosen futures to main, "
      f"credited {n_credit} explored futures by EV gap")
print("store now:", store.count_commits(), "gems;",
      len(store.list_branches(prefix='frontier/')), "frontier branches")
