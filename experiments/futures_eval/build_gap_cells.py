"""Fill the last master cells EXPERIMENTALLY (no interpolation).

LLM arms (prompts built here, run by sub-agents):
  * R9-flat    — rules stated + ALL 15 past-game records (flat file) + scenarios
  * R9-vector  — rules stated + per-scenario TOP-5 SIMILAR records + scenarios
  * R10-vector — rules NOT stated + per-scenario TOP-5 SIMILAR records only
                 (must infer the machine from a retrieved sample)

Mechanical measurements (run here, scored like any policy):
  * R9-exact   — the mechanical apparatus executed as a policy: enumerate
                 rollouts with the stated rules, argmax EV; score its picks.
  * R10-exact  — genuine rule-FITTING: candidate freeze/day-2 hypotheses tested
                 against the 15 records; plan with the surviving rule; score.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from build_eval import PLAYERS, simulate, transcript, gen_scenario, mine, RULES  # noqa: E402
from build_inferred import narrate_past_game  # noqa: E402

meta = json.load(open(ROOT / "meta.json"))


# ---- past-game records (same 15 as the inferred experiment) -----------------
def past_records():
    r = random.Random(31)
    recs = []
    idx = 0
    while idx < 15:
        belief, accusers = gen_scenario(5000 + idx * 7)
        wolf = r.choice(PLAYERS)
        vote = wolf if idx % 5 == 0 else r.choice([p for p in PLAYERS if p != wolf])
        txt, _ = narrate_past_game(idx, belief, accusers, vote, wolf)
        recs.append((txt, belief, accusers, vote, wolf))
        idx += 1
    return recs


def feats(accusers):
    return {(a, t) for t, accs in accusers.items() for a in accs}


def topk_records(recs, accusers, k=5):
    f = feats(accusers)
    return sorted(recs, key=lambda r: -len(f & feats(r[2])))[:k]


def build_llm_prompts():
    recs = past_records()
    traps, controls = mine()
    scenarios = traps + controls
    all_recs = "\n\n".join(r[0] for r in recs)

    ask = ("For EACH scenario pick the Day-1 vote that MAXIMIZES expected final "
           "score. Return ONLY JSON {\"S0\":\"Px\",...}.\n\n")
    p_flat9 = RULES + ("\nYou also have your flat notes file of past games:\n\n"
                       + all_recs + "\n\n" + ask)
    p_vec9 = RULES + ("\nFor each scenario, your memory system retrieved the 5 "
                      "most similar past games.\n\n" + ask)
    p_vec10 = ("You are P0; your Day-1 vote decides who the village eliminates. "
               "The mechanics after a wrong vote are NOT stated — infer them "
               "from the retrieved past games (5 most similar per scenario).\n\n"
               + ask)
    for k, (seed, belief, accusers, evs, myopic, best, gap) in enumerate(scenarios):
        blk = (f"=== SCENARIO S{k} ===\nDay-1 statements:\n{transcript(accusers)}\n"
               f"Your belief: {json.dumps(belief)}\n")
        p_flat9 += blk + "\n"
        sim_blk = blk + "  Retrieved similar past games:\n" + "\n\n".join(
            "  " + r[0].replace("\n", "\n  ") for r in topk_records(recs, accusers)) + "\n\n"
        p_vec9 += sim_blk
        p_vec10 += sim_blk
    (ROOT / "prompt_flat9.txt").write_text(p_flat9)
    (ROOT / "prompt_vec9.txt").write_text(p_vec9)
    (ROOT / "prompt_vec10.txt").write_text(p_vec10)
    print("LLM prompts (KB):", {n: round((ROOT / f'prompt_{n}.txt').stat().st_size / 1024, 1)
                                for n in ("flat9", "vec9", "vec10")})


# ---- mechanical: R9-exact (stated rules -> enumerate -> argmax EV) ----------
def r9_exact():
    traps, controls = mine()
    ev = 0.0
    opt = 0
    for k, (seed, belief, accusers, evs, myopic, best, gap) in enumerate(traps + controls):
        table = {v: sum(belief[w] * simulate(v, w, belief, accusers)[0] for w in PLAYERS)
                 for v in PLAYERS}
        pick = max(table, key=table.get)
        m = meta[f"S{k}"]
        ev += m["evs"][pick] / 12
        opt += pick == m["best"]
    return round(ev, 3), opt


# ---- mechanical: R10-exact (FIT the rule from records, then plan) -----------
def fit_freeze_rule(recs):
    """Test candidate freeze rules against every recorded miss-game freeze."""
    def observed_freeze(txt):
        for ln in txt.splitlines():
            if "was frozen" in ln:
                return ln.split(",")[1].strip().split(" ")[0]
        return None

    cands = {
        "accuser_else_topbelief": lambda rem, wolf, acc, bel:
            ([a for a in acc.get(wolf, []) if a in rem and a != wolf] or
             [sorted((p for p in rem if p != wolf), key=lambda p: -bel[p])[0]])[0],
        "topbelief_always": lambda rem, wolf, acc, bel:
            sorted((p for p in rem if p != wolf), key=lambda p: -bel[p])[0],
        "accuser_else_lowbelief": lambda rem, wolf, acc, bel:
            ([a for a in acc.get(wolf, []) if a in rem and a != wolf] or
             [sorted((p for p in rem if p != wolf), key=lambda p: bel[p])[0]])[0],
        "lowbelief_always": lambda rem, wolf, acc, bel:
            sorted((p for p in rem if p != wolf), key=lambda p: bel[p])[0],
    }
    surviving = dict(cands)
    for txt, belief, accusers, vote, wolf in recs:
        if vote == wolf:
            continue
        obs = observed_freeze(txt)
        rem = [p for p in PLAYERS if p != vote]
        for name in list(surviving):
            if surviving[name](rem, wolf, accusers, belief) != obs:
                del surviving[name]
    return surviving


def r10_exact():
    recs = past_records()
    surviving = fit_freeze_rule(recs)
    assert len(surviving) >= 1, "no consistent rule — fitting failed"
    name, rule = next(iter(surviving.items()))

    def sim_fitted(vote, wolf, belief, accusers):
        if vote == wolf:
            return 1.0
        rem = [p for p in PLAYERS if p != vote]
        frozen = rule(rem, wolf, accusers, belief)
        pool = [p for p in rem if p != frozen]
        return 0.6 if max(pool, key=lambda p: belief[p]) == wolf else 0.0

    traps, controls = mine()
    ev = 0.0
    opt = 0
    for k, (seed, belief, accusers, evs, myopic, best, gap) in enumerate(traps + controls):
        table = {v: sum(belief[w] * sim_fitted(v, w, belief, accusers) for w in PLAYERS)
                 for v in PLAYERS}
        pick = max(table, key=table.get)
        m = meta[f"S{k}"]
        ev += m["evs"][pick] / 12
        opt += pick == m["best"]
    return round(ev, 3), opt, sorted(surviving)


if __name__ == "__main__":
    build_llm_prompts()
    ev9, opt9 = r9_exact()
    print(f"R9-exact (mechanical EV policy, executed): EV={ev9} optimal={opt9}/12")
    ev10, opt10, rules_fit = r10_exact()
    print(f"R10-exact (rule FITTED from 15 records: {rules_fit}): "
          f"EV={ev10} optimal={opt10}/12")
    json.dump({"r9_exact_ev": ev9, "r10_exact_ev": ev10, "fitted_rules": rules_fit},
              open(ROOT / "result_mechanical.json", "w"), indent=1)
