"""Small real-agent confirmation for the beyond-context scale demo.

Same decision, three ways of accessing an 800K-record career history:
  * gemmery — the index's exact answer: each player's set of roles EVER truly held
  * md      — a big readable SLICE of the raw notes.md (as much as fits), infer support
  * cold    — no memory
All apply the same rule: a claim is a lie (=> Gnosia) iff the player has never
truly held that role.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scale_demo import (generate, make_tests, build_index, index_support,  # noqa: E402
                        record_line, PERSONAS, ROLES)

N_LLM_TESTS = 6
MD_SLICE_RECORDS = 8000  # a hefty "read as much as fits" chunk (~1% of history)

defs, rare_games, records = generate()
con = build_index(records)
tests = make_tests(defs, records)[:N_LLM_TESTS]

truth = {t["id"]: t["gnosia"] for t in tests}
json.dump(truth, open(ROOT / "llm_truth.json", "w"), indent=1)

RULE = ("Rule: each game has hidden Gnosia. A player who CLAIMS a power role is "
        "LYING (=> a Gnosia) if they have NEVER truly held that role in their "
        "career; if they have held it (even rarely) the claim is honest. For each "
        "game, name the ONE player whose claim is a lie.\n"
        "Return ONLY JSON mapping game id -> player, e.g. {\"T0\":\"P3\"}.\n\n")


def games_block():
    b = ""
    for t in tests:
        cl = ", ".join(f"{p} claims {r}" for p, r in sorted(t["claims"].items()))
        b += f"===== GAME {t['id']} =====\nThis game: {cl}\n\n"
    return b


# gemmery: exact per-player career role support (what the index returns)
support_tbl = "\n".join(
    f"  {p}: has truly held {sorted(index_support(con, p)) or ['(no power role on record)']}"
    for p in PERSONAS)
(ROOT / "prompt_gemmery.txt").write_text(
    RULE + "MEMORY (index query — each player's roles ever truly held, exact over "
    "the whole career):\n" + support_tbl + "\n\n" + games_block())

# md: a big slice of the raw notes the reader could hold. Rule + games FIRST so a
# truncating reader still sees the questions, then as many raw records as fit.
slice_txt = "\n".join(record_line(r) for r in records[:MD_SLICE_RECORDS])
(ROOT / "prompt_md.txt").write_text(
    RULE + games_block()
    + f"MEMORY (an excerpt of your notes.md — the first {MD_SLICE_RECORDS:,} of "
    f"{len(records):,} career records; the rest do not fit in context. You may "
    f"also grep this excerpt for a player):\n" + slice_txt + "\n")

# cold
(ROOT / "prompt_cold.txt").write_text(RULE + "(You have no memory of past games.)\n\n" + games_block())

print(f"built LLM confirmation: {len(tests)} games, 3 arms")
print("prompt sizes (KB):", {a: round((ROOT / f'prompt_{a}.txt').stat().st_size / 1024)
                             for a in ("gemmery", "md", "cold")})
