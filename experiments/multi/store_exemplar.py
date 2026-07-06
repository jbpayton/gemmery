"""Seed-0 exemplar on the REAL store: branches as perspectives, conflicts
surfaced by cross-branch reads, adjudicated select_to_main, outcome tags.
Asserts exact parity with the python simulation's adjudicated answers.
"""
import math, random, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
sys.path.insert(0, str(ROOT))
from gemmery import Action, Gem, IndexKeys, Kind, KnowledgeBody, Provenance, GitStore
import harness as H

if (ROOT / "store").exists():
    shutil.rmtree(ROOT / "store")
st = GitStore(ROOT / "store")
seed_gem = Gem(kind=Kind.knowledge, provenance=Provenance("world", "setup"),
               body=KnowledgeBody(action=Action("init", {}), reasoning="the shared case file",
                                  belief="90 hidden facts"),
               index_keys=IndexKeys(action_type="setup", domain=["multi"]))
st.capture(seed_gem, path="case/setup")
branches = [st.branch_frontier(f"agent-{i}") for i in range(H.N)]

rng = random.Random(0)
truth = [rng.random() < 0.5 for _ in range(H.K)]
obs = [[[] for _ in range(H.K)] for _ in range(H.N)]
credit = [[0, 0] for _ in range(H.N)]
order = list(range(H.K)); rng.shuffle(order)
py = [r for r in H.run_seed(0) if "solo" in r]   # reference answers

def claim_gem(i, k):
    h = obs[i][k]
    cl = sum(h) * 2 > len(h) or (sum(h) * 2 == len(h) and h[-1])
    return cl, Gem(kind=Kind.knowledge, provenance=Provenance(f"agent-{i}", f"fact-{k}"),
                   body=KnowledgeBody(action=Action("claim", {"fact": k, "n_obs": len(h)}),
                                      reasoning=f"my observations of f{k}: {h}",
                                      belief=f"f{k}={cl}"),
                   index_keys=IndexKeys(action_type="claim", domain=[f"agent-{i}"]))

adjud_answers, conflicts_surfaced, selections = [], 0, 0
qi = 0
for t in range(H.T):
    for i in range(H.N):
        for k in rng.sample(range(H.K), H.M):
            seen = truth[k] if rng.random() < H.RELS[i] else not truth[k]
            obs[i][k].append(seen)
            cl, g = claim_gem(i, k)
            path = f"facts/f{k}"
            if len(obs[i][k]) == 1:
                st.capture(g, branch=branches[i], path=path)
            else:
                st.revise(g, path, branch=branches[i])
    q = order[t]
    # --- conflict surfacing: read every perspective at the queried path ---
    tips, claims = {}, {}
    for i in range(H.N):
        hist = st.history(f"facts/f{q}", branch=branches[i])
        if hist:
            g = st.read_gem(hist[0])
            claims[i] = g.body.belief.endswith("True")
            tips[i] = hist[0]
    if not claims:
        continue
    vals = set(claims.values())
    if len(vals) > 1:
        conflicts_surfaced += 1
        s = 0.0
        for i, v in claims.items():
            w = min(max((credit[i][0] + 1) / (credit[i][1] + 2), 0.02), 0.98)
            s += math.log(w / (1 - w)) * (1 if v else -1)
        ans = s > 0 or abs(s) <= 1e-12
        winner = max((i for i, v in claims.items() if v == ans),
                     key=lambda i: (credit[i][0] + 1) / (credit[i][1] + 2))
        st.select_to_main(tips[winner])       # adjudicated merge, losers stay on branch
        selections += 1
    else:
        ans = next(iter(vals))
    adjud_answers.append(ans == truth[q])
    for i, v in claims.items():
        st.tag_outcome(tips[i], f"reveal-f{q}", ok=(v == truth[q]))
        credit[i][1] += 1; credit[i][0] += (v == truth[q])
    qi += 1

ref = [r["adjud"] for r in py]
assert adjud_answers == ref, f"PARITY FAIL: {sum(a!=b for a,b in zip(adjud_answers,ref))} mismatches"
print(f"PARITY OK: {len(adjud_answers)} store-backed answers == simulation exactly")
print(f"conflicts surfaced: {conflicts_surfaced}; adjudicated selections to main: {selections}")
print(f"store: {st.count_commits()} gems across main + {len(branches)} perspective branches")
# post-hoc: one worked conflict
q0 = next(r for r in py if r.get("conflict"))
print(f"\nexample: fact f{order[q0['t']]} was conflicted at t={q0['t']}; "
      f"main holds the adjudicated winner, every losing perspective remains "
      f"readable on its agent's branch (git log -- facts/f{order[q0['t']]})")
