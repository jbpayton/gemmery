"""Real-agent confirmation: in-context induction of a complex behavioral rule,
and whether SIMILAR examples (retrieval) beat a RANDOM sample."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from rules_demo import make_rule, sample_data, NOISE, N_FEATURES  # noqa: E402

N_EXAMPLES = 40
N_TEST = 20

rule = make_rule(1000)
Xtr, ytr = sample_data(rule, 2500, NOISE, seed=0)
Xte, yte = sample_data(rule, N_TEST, NOISE, seed=777)
bits = lambda x: "".join(map(str, x))

truth = {f"Q{i}": int(yte[i]) for i in range(N_TEST)}
json.dump(truth, open(ROOT / "llm_truth.json", "w"), indent=1)

RULE = (
    f"A person decides 0 or 1 in each situation, described by {N_FEATURES} binary "
    "features. They follow a FIXED but COMPLEX internal rule (it depends on several "
    "features together, not one), and obey it about 85% of the time (they "
    "occasionally deviate). Using the example situations->decisions, predict the "
    "person's MOST LIKELY decision for each query situation.\n"
    "Return ONLY JSON mapping each query id to 0 or 1, e.g. {\"Q0\":1,\"Q1\":0}.\n\n")

# md / random: one shared random sample of the person's history
rng = np.random.RandomState(5)
ridx = rng.choice(len(Xtr), N_EXAMPLES, replace=False)
rand_block = "\n".join(f"  {bits(Xtr[j])} -> {ytr[j]}" for j in ridx)
md = RULE + f"EXAMPLES ({N_EXAMPLES} random past situations for this person):\n" + rand_block + "\n\n"
for i in range(N_TEST):
    md += f"Q{i}: situation {bits(Xte[i])} -> ?\n"
(ROOT / "prompt_md.txt").write_text(md)

# gemmery / similar: for each query, its nearest past situations (retrieval)
gem = RULE + "For each query you are given the most SIMILAR past situations for "
gem += "this person (retrieved from memory):\n\n"
for i in range(N_TEST):
    d = np.sum(Xtr != Xte[i], axis=1)
    nn = np.argpartition(d, N_EXAMPLES)[:N_EXAMPLES]
    gem += f"Q{i}: situation {bits(Xte[i])} -> ?\n  most similar past situations:\n"
    gem += "\n".join(f"    {bits(Xtr[j])} -> {ytr[j]}" for j in nn) + "\n\n"
(ROOT / "prompt_gemmery.txt").write_text(gem)

# cold: no examples
cold = RULE + "(You have no examples of this person.)\n\n"
for i in range(N_TEST):
    cold += f"Q{i}: situation {bits(Xte[i])} -> ?\n"
(ROOT / "prompt_cold.txt").write_text(cold)

print("built:", N_TEST, "queries, 3 arms")
print("sizes KB:", {a: round((ROOT / f"prompt_{a}.txt").stat().st_size / 1024, 1)
                    for a in ("gemmery", "md", "cold")})
print("class balance in truth:", sum(truth.values()), "/", N_TEST)
