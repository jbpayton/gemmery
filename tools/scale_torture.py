"""P2 scale torture: 100K gems in one store.

Measures what production cares about: capture latency vs store size (the
<25ms invariant), history() on a 1000-deep dossier, ls, read_gem, notes
fold, repo size before/after gc. Day-sharded paths (the default policy)
so no directory grows unbounded.
"""
import json, statistics, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gemmery import Action, DecisionBody, Gem, IndexKeys, Kind, Provenance, GitStore  # noqa

N = 100_000
REVISED_PATH = "knowledge/hot-dossier"
out = ROOT / "tools" / "scale_results.json"

def gem(i, day):
    return Gem(kind=Kind.decision,
               provenance=Provenance("scale", f"g{i}", timestamp=day * 86400 + 1_600_000_000),
               body=DecisionBody(action=Action("act", {"i": i}),
                                 reasoning=f"decision {i}: the usual sixty-word rationale "
                                           f"about why option A beat option B on evidence."),
               index_keys=IndexKeys(action_type="act", domain=["scale"]))

store_dir = ROOT / ".scale-store"
if store_dir.exists():
    subprocess.run(["rm", "-rf", str(store_dir)])
st = GitStore(store_dir)

lat, marks = [], {}
t0 = time.time()
for i in range(N):
    day = i // 1000                       # ~1000 gems/day-shard
    r = st.capture(gem(i, day))
    lat.append(r.capture_ms)
    if i % 100 == 37:                     # interleave revisions of one path
        st.revise(gem(i, day), REVISED_PATH)
    if (i + 1) % 10_000 == 0:
        dec = lat[-10_000:]
        marks[i + 1] = {"median_ms": round(statistics.median(dec), 2),
                        "p99_ms": round(sorted(dec)[int(0.99 * len(dec))], 2)}
        print(f"{i+1:7d} captures: median {marks[i+1]['median_ms']}ms "
              f"p99 {marks[i+1]['p99_ms']}ms  ({time.time()-t0:.0f}s elapsed)", flush=True)

def timed(fn, reps=5):
    ts = []
    for _ in range(reps):
        a = time.perf_counter(); fn(); ts.append((time.perf_counter() - a) * 1000)
    return round(statistics.median(ts), 1)

res = {"n": N, "capture_curve": marks,
       "median_all_ms": round(statistics.median(lat), 2),
       "invariant_25ms_ok": statistics.median(lat[-10_000:]) < 25.0}
hist = st.history(REVISED_PATH)
res["revision_depth"] = len(hist)
res["history_1000deep_ms"] = timed(lambda: st.history(REVISED_PATH))
res["read_gem_ms"] = timed(lambda: st.read_gem(hist[0]))
res["ls_day_shard_ms"] = timed(lambda: st.ls("decision/1970-04-27") or st.ls("decision"))
sz = subprocess.run(["du", "-sm", str(store_dir)], capture_output=True, text=True)
res["repo_mb_pre_gc"] = int(sz.stdout.split()[0])
t = time.time(); subprocess.run(["git", "-C", str(store_dir), "gc", "--quiet"]); res["gc_s"] = round(time.time() - t, 1)
sz = subprocess.run(["du", "-sm", str(store_dir)], capture_output=True, text=True)
res["repo_mb_post_gc"] = int(sz.stdout.split()[0])
res["history_post_gc_ms"] = timed(lambda: st.history(REVISED_PATH))
res["capture_post_gc_ms"] = timed(lambda: st.capture(gem(N + 1, 101)), reps=3)
json.dump(res, open(out, "w"), indent=1)
print(json.dumps(res, indent=1))
