"""Capture the focal's per-round decisions as gems in git, credit the memory that
was load-bearing, then emit the post-hoc 'why' trace + an explainer prompt.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from gemmery import (Action, Cost, DecisionBody, Gem, GitStore, IndexKeys,  # noqa: E402
                     Kind, Provenance, TestSpec)

STORE = ROOT / "store"
TS = 1_700_100_100


def load(name):
    t = (ROOT / "out" / name).read_text().strip()
    if "```" in t:
        t = t.split("```")[1].lstrip("json").strip()
    return json.loads(t)


def main():
    game = json.load(open(ROOT / "game.json"))
    wolf, mem = game["wolf"], game["mem_sha"]
    store = GitStore(STORE, actor="focal-P0", email="p0@gemmery.local")

    prev = None
    decisions = []
    for r in (1, 2):
        a = load(f"round{r}.json")
        consumed = [mem[p] for p in a.get("used_memory", []) if p in mem]
        belief = a.get("belief", {})
        belief_str = ", ".join(f"{k}:{v}" for k, v in belief.items())
        g = Gem(kind=Kind.decision,
                provenance=Provenance("focal-P0", "game", timestamp=TS + r),
                body=DecisionBody(
                    action=Action("accuse", {"target": a["guess"], "round": r}),
                    reasoning=f"Round {r}. Accuse {a['guess']}. Belief [{belief_str}]. "
                              f"{a.get('reasoning','')}",
                    tests=[TestSpec("accusation_correct", "reveal at game end", "target is the wolf")],
                    pre={"round": r, "belief": belief}),
                cost=Cost(),
                consumed=consumed,
                incited_by=prev,
                index_keys=IndexKeys(action_type="accuse", domain=[a["guess"]],
                                     precondition_shape=["round" + str(r)],
                                     test_ids=["accusation_correct"]))
        sha = store.capture(g, branch="main", path=f"decisions/round{r}").sha
        decisions.append((r, sha, a, consumed))
        prev = sha

    # reveal + score the final decision; credit the tells that were load-bearing
    final_r, final_sha, final_a, final_consumed = decisions[-1]
    correct = final_a["guess"] == wolf
    store.attach_success(final_sha, "accusation_correct", 1.0 if correct else -1.0, source="reveal")
    store.tag_outcome(final_sha, "accusation_correct", ok=correct)
    for tell_sha in final_consumed:                     # credit flows to load-bearing memory
        store.attach_credit(tell_sha, 1.0 if correct else -0.5, source_sha=final_sha, test="accusation_correct")

    # build the post-hoc trace from the DAG (dossier headline + wolf-tell section)
    def headline(text):
        lines = [ln for ln in text.splitlines() if ln.strip()]
        tell = ""
        for i, ln in enumerate(lines):
            if ln.startswith("## Wolf tell") and i + 1 < len(lines):
                tell = lines[i + 1]
                break
        return f"{lines[0]} — {tell}"

    facts = {p: headline(store.read_gem(sha).reasoning_text()) for p, sha in mem.items()}
    trace_lines = [f"Reveal: the werewolf was {wolf}. Final call: {final_a['guess']} "
                   f"({'CORRECT' if correct else 'WRONG'}).\n"]
    for r, sha, a, consumed in decisions:
        trace_lines.append(f"Round {r} decision (gem {sha[:10]}): accuse {a['guess']}, "
                           f"belief {a.get('belief')}")
        trace_lines.append(f"  reasoning: {a.get('reasoning','')}")
        used = [p for p in mem if mem[p] in consumed]
        for p in used:
            trace_lines.append(f"  consumed memory [{p} tell]: {facts[p]}")
        trace_lines.append("")
    trace = "\n".join(trace_lines)
    (ROOT / "trace.txt").write_text(trace)

    # credit summary on the memory
    cred = {p: store.notes(mem[p])["credit"]["total"] for p in mem}
    json.dump({"wolf": wolf, "correct": correct, "final_guess": final_a["guess"],
               "decision_shas": [d[1] for d in decisions], "memory_credit": cred},
              open(ROOT / "result.json", "w"), indent=1)

    explainer_prompt = (
        "Below is the git record of how the player P0 played one game of Werewolf: "
        "each decision, the belief at the time, the memory it consumed, and the final "
        "outcome. Write a concise POST-HOC analysis answering 'why did we play the way "
        "we did?' — round by round, citing the specific tells that were load-bearing, "
        "and noting how a memoryless player would have been fooled here. 2 short "
        "paragraphs.\n\n" + trace)
    (ROOT / "prompt_explainer.txt").write_text(explainer_prompt)

    print(f"captured {len(decisions)} decision gems; final={final_a['guess']} "
          f"({'correct' if correct else 'wrong'}); wolf={wolf}")
    print("memory credit after the game:", {p: round(c, 2) for p, c in cred.items()})
    print("\n--- post-hoc trace (from git) ---\n" + trace)


if __name__ == "__main__":
    main()
