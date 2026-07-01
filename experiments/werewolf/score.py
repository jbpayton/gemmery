"""Score the LLM-focal Werewolf memory experiment: memory arm vs cold arm."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
truth = json.load(open(ROOT / "truth.json"))


def load(arm):
    p = ROOT / f"answer_{arm}.json"
    if not p.exists():
        return {}
    txt = p.read_text().strip()
    if "```" in txt:  # tolerate fenced json
        txt = txt.split("```")[1].lstrip("json").strip()
    return json.loads(txt)


mem, cold = load("memory"), load("cold")
gids = sorted(truth, key=lambda g: int(g[1:]))  # by game index = memory size

print(f"{'game':>5} {'mem_size':>8}  {'truth':>5}  {'memory':>7}  {'cold':>5}")
print("-" * 40)
mem_ok = cold_ok = 0
for gid in gids:
    k = int(gid[1:])
    t = truth[gid]
    m = mem.get(gid, "?"); c = cold.get(gid, "?")
    mem_ok += (m == t); cold_ok += (c == t)
    print(f"{gid:>5} {k:>8}  {t:>5}  {m:>7}{'✓' if m==t else '✗'}  {c:>4}{'✓' if c==t else '✗'}")

n = len(gids)
print("-" * 40)
print(f"chance = 0.25")
print(f"LLM focal + MEMORY:  {mem_ok}/{n} = {mem_ok/n:.2f}")
print(f"LLM focal + COLD:    {cold_ok}/{n} = {cold_ok/n:.2f}")
print(f"memory effect (Δ):   {(mem_ok-cold_ok)/n:+.2f}")

# learning view: accuracy on later (memory-rich) games
late = [g for g in gids if int(g[1:]) >= 20]
if late:
    lm = sum(mem.get(g) == truth[g] for g in late) / len(late)
    lc = sum(cold.get(g) == truth[g] for g in late) / len(late)
    print(f"on memory-rich games (idx>=20): memory={lm:.2f} cold={lc:.2f}")

json.dump({"memory_acc": mem_ok / n, "cold_acc": cold_ok / n,
           "n": n, "per_game": {g: {"truth": truth[g], "memory": mem.get(g),
                                    "cold": cold.get(g)} for g in gids}},
          open(ROOT / "result.json", "w"), indent=1)
print("\nwrote result.json")
