"""Beyond-the-context-window: when structure becomes *mandatory*, not optional.

Every prior experiment let a flat markdown scratchpad tie Gemmery, because the
whole history still fit in a context window — so "read it all" worked. This
experiment removes that escape: the decision hinges on a **rare-event existence
fact** scattered across a career history far larger than any context window.

The task ("alibi check"): you have played tens of thousands of games with the
same 8 opponents. This game, a player claims a power role. Is it a lie? It is a
lie — marking them a Gnosia — iff that opponent has **never once** truly held
that role in their entire recorded career. An honest player may be claiming a
role they hold only *rarely* (a handful of times across the whole history).

Why this defeats read-based memory: any context-bounded reader can only see a
*slice* of the history, and a rare clear (say 5 games out of 100,000) is very
likely *outside* that slice — so the reader wrongly concludes "never held it"
and accuses an innocent player. Gemmery's derived index answers the exact
existence/aggregate query (`SELECT DISTINCT true_role WHERE player=p`) over the
whole store in O(index), regardless of context size. Structure stops being a
convenience and becomes the only thing that works.

No git commits at this scale (that would be hundreds of thousands of commits) —
we bulk-load the columnar index directly. That is legitimate: the index is
"derived and disposable" by design (Invariant 6); at real scale Gemmery captures
in batches and rebuilds the index from the store. The point here is the
*retrieval* layer.
"""

from __future__ import annotations

import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROLES = ["Engineer", "Doctor", "GuardianAngel", "Guard"]
PERSONAS = [f"P{i}" for i in range(8)]

GAMES = 100_000
RARE_HOLDS = 5          # times each persona truly holds its RARE role, in all of history
N_TEST = 40
CHARS_PER_TOKEN = 4     # rough
CONTEXT_TOKENS = 200_000  # a large context window, for reference


def persona_roles():
    """Each persona: a COMMON role (held often), a RARE role (held RARE_HOLDS
    times total), and 2 NEVER roles. Support = {common, rare}."""
    defs = {}
    for i, p in enumerate(PERSONAS):
        r = random.Random(500 + i)
        roles = r.sample(ROLES, len(ROLES))
        defs[p] = {"common": roles[0], "rare": roles[1], "never": roles[2:]}
    return defs


def generate(games=GAMES):
    """Return records [(g, player, is_gnosia, true_role, claimed_role)] and the
    per-persona set of games in which they truly hold their RARE role."""
    defs = persona_roles()
    rng = random.Random(12345)
    rare_games = {p: set(rng.sample(range(games), RARE_HOLDS)) for p in PERSONAS}
    records = []
    for g in range(games):
        gr = random.Random(g)
        gnosia = set(gr.sample(PERSONAS, 2))
        for p in PERSONAS:
            d = defs[p]
            if p in gnosia:
                claimed = gr.choice(d["never"]) if gr.random() < 0.85 else None
                records.append((g, p, 1, "Gnosia", claimed))
            else:
                if g in rare_games[p]:
                    true_role = d["rare"]           # the rare, alibi-clearing hold
                elif gr.random() < 0.55:
                    true_role = d["common"]
                else:
                    true_role = "Crew"
                claimed = true_role if (true_role in ROLES and gr.random() < 0.7) else None
                records.append((g, p, 0, true_role, claimed))
    return defs, rare_games, records


def record_line(rec) -> str:
    g, p, is_g, true_role, claimed = rec
    return (f"g{g}: {p} was {'GNOSIA' if is_g else true_role}; "
            f"claimed {claimed or 'nothing'}.")


# --------------------------------------------------------------------------- #
# Gemmery-style columnar index (bulk-loaded) — the derived retrieval layer.
# --------------------------------------------------------------------------- #
def build_index(records) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE rec(g INT, player TEXT, is_gnosia INT, true_role TEXT, claimed TEXT)")
    con.executemany("INSERT INTO rec VALUES(?,?,?,?,?)", records)
    con.execute("CREATE INDEX i_player ON rec(player, true_role)")
    con.commit()
    return con


def index_support(con, player) -> set:
    """Exact: the set of power-roles this player has EVER truly held (O(index))."""
    rows = con.execute(
        "SELECT DISTINCT true_role FROM rec WHERE player=? AND true_role IN "
        "('Engineer','Doctor','GuardianAngel','Guard')", (player,))
    return {r[0] for r in rows}


def window_support(records_slice, player) -> set:
    """What a context-bounded reader can infer from the slice it can see."""
    return {r[3] for r in records_slice if r[1] == player and r[3] in ROLES}


# --------------------------------------------------------------------------- #
# Test games: a Gnosia claiming a NEVER role vs an honest player claiming their
# RARE role. Both look like liars unless you know the rare alibi.
# --------------------------------------------------------------------------- #
def make_tests(defs, records, n=N_TEST):
    rng = random.Random(999)
    tests = []
    people = PERSONAS[:]
    for t in range(n):
        rng.shuffle(people)
        gnosia_liar, honest_rare = people[0], people[1]
        claims = {
            gnosia_liar: rng.choice(defs[gnosia_liar]["never"]),   # true lie
            honest_rare: defs[honest_rare]["rare"],                 # true, but rare
        }
        # a couple of clearly-honest common claims as noise
        for p in people[2:4]:
            claims[p] = defs[p]["common"]
        tests.append({"id": f"T{t}", "claims": claims,
                      "gnosia": gnosia_liar, "honest_rare": honest_rare})
    return tests


def accuse(claims, support_fn, rng) -> str:
    """Accuse a claimant whose claimed role is NOT in their (estimated) support —
    a role they've never been *seen* to truly hold. If several look like liars
    (e.g. the reader also can't vouch for an honest player's rare role), it must
    guess among them — that guess is where a context-bounded reader loses."""
    liars = [p for p, r in claims.items() if r not in support_fn(p)]
    pool = liars if liars else list(claims)
    return rng.choice(sorted(pool))  # sorted -> order can't leak the answer


def run_deterministic():
    defs, rare_games, records = generate()
    con = build_index(records)
    tests = make_tests(defs, records)

    total_chars = sum(len(record_line(r)) + 1 for r in records)
    total_tokens = total_chars // CHARS_PER_TOKEN

    def index_fn(p):
        return index_support(con, p)

    # window: the reader sees the first W records that fit a context budget
    def window_fn_factory(frac):
        w = max(1, int(len(records) * frac))
        sl = records[:w]
        return lambda p: window_support(sl, p)

    def score(support_fn, seed=0):
        rng = random.Random(seed)
        ok = sum(accuse(t["claims"], support_fn, rng) == t["gnosia"] for t in tests)
        return ok / len(tests)

    frac_window = (CONTEXT_TOKENS / total_tokens) if total_tokens else 1.0
    results = {
        "total_records": len(records),
        "total_chars": total_chars,
        "total_tokens_est": total_tokens,
        "context_tokens": CONTEXT_TOKENS,
        "history_over_context_x": round(total_tokens / CONTEXT_TOKENS, 1),
        "window_fraction_that_fits": round(frac_window, 4),
        "acc_index_exact": score(index_fn),
        "acc_window_fits_context": score(window_fn_factory(min(1.0, frac_window))),
        "acc_cold_random": None,
    }
    # cold: no memory -> random guess among claimants
    rng = random.Random(7)
    results["acc_cold_random"] = sum(
        rng.choice(list(t["claims"])) == t["gnosia"] for t in tests) / len(tests)

    # accuracy vs readable fraction (the money curve)
    curve = []
    for frac in [0.01, 0.02, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0]:
        curve.append((frac, score(window_fn_factory(frac))))
    results["curve"] = curve
    return defs, records, con, tests, results


if __name__ == "__main__":
    defs, records, con, tests, res = run_deterministic()
    mb = res["total_chars"] / 1e6
    print(f"history: {res['total_records']:,} records  ~{mb:.1f} MB  "
          f"~{res['total_tokens_est']:,} tokens")
    print(f"that is ~{res['history_over_context_x']}x a {res['context_tokens']:,}-token "
          f"context window; a reader can hold ~{res['window_fraction_that_fits']*100:.1f}% of it")
    print()
    print(f"accuracy (name the Gnosia, chance ~0.25-0.5):")
    print(f"  cold (no memory):            {res['acc_cold_random']:.2f}")
    print(f"  markdown read (fits context): {res['acc_window_fits_context']:.2f}")
    print(f"  Gemmery index (exact query):  {res['acc_index_exact']:.2f}")
    print()
    print("accuracy vs fraction of history readable:")
    for frac, acc in res["curve"]:
        marker = "  <- fits a context window" if frac <= res["window_fraction_that_fits"] * 1.6 and frac >= res["window_fraction_that_fits"] * 0.6 else ""
        print(f"  {frac*100:5.1f}% : {acc:.2f}{marker}")
