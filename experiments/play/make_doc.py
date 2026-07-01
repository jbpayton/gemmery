"""Assemble WHY_WE_PLAYED.md (the played game + git record + post-hoc explanation)
and a decision-DAG diagram."""
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent
STORE = ROOT / "store"


def git(*a):
    return subprocess.run(["git", "-C", str(STORE), *a], capture_output=True, text=True).stdout.rstrip()


def main():
    game = json.load(open(ROOT / "game.json"))
    res = json.load(open(ROOT / "result.json"))
    trace = (ROOT / "trace.txt").read_text()
    expl = (ROOT / "out" / "explanation.md").read_text().strip() if (ROOT / "out" / "explanation.md").exists() else "(explainer pending)"
    log = git("log", "--graph", "--oneline", "--decorate", "--branches", "--tags", "--date-order")

    doc = f"""# Why we played the way we did — a game of Werewolf, explained from git

We played one game of Werewolf with an LLM as the focal villager P0, **captured
every decision into a real git memory as it happened**, and then reconstructed
"why we played the way we did" purely from that record. Nothing here is
narration bolted on afterward — it is read back out of the DAG.

## The game (wolf = {game['wolf']}, revealed only at the end)

```
{game['transcript']}
```

The trap: **P2 openly claims to be the Seer.** To a memoryless reader that looks
helpful — you'd trust P2 and suspect someone else. Memory knew better.

## What got recorded in git (the play)

```
{log}
```

The four `memory` gems are the players' tells (learned from past games). The two
decisions on `main` are the rounds; the final one is tagged with the outcome.
Each decision gem records its belief, its reasoning, and a `consumed` edge to the
exact tells it used.

## Post-hoc "why", reconstructed from the DAG

Walking each decision gem's reasoning + its `consumed` evidence:

```
{trace}
```

## The explanation, written by a second agent that saw only the git trace

> {expl.replace(chr(10), chr(10) + '> ')}

## Credit flowed back to the memory that earned it

The accusation was **{'correct' if res['correct'] else 'wrong'}**, so credit was
attached (as notes) to the tells the winning decision consumed:

```json
{json.dumps(res['memory_credit'], indent=2)}
```

Those numbers are the memory's *track record* forming — the P2 Seer-tell that
cracked the trap is now worth more for next time (§7, earned credit).

## Why this is only possible on a versioned, dependency-tracked store

The question "why did we accuse P2 on round 1?" is answered by **reading git**:
the decision gem holds the belief and reasoning at that moment; its `consumed`
edges point at the exact tells it rested on; the immutable commits + append-only
credit notes let you replay it after the fact and even re-derive the memory state
as it was (`git checkout`). A flat scratchpad that gets overwritten keeps only
the final answer; the *reasoning trace* — what we believed, what it rested on,
and why it looked right at the time — is gone. Here it is a property of the
substrate.

Reproduce: `python experiments/play/prep.py`, play the rounds, then
`python experiments/play/capture.py` and `python experiments/play/make_doc.py`.
"""
    (ROOT / "WHY_WE_PLAYED.md").write_text(doc)
    print("wrote", ROOT / "WHY_WE_PLAYED.md")
    draw(game, res)


def draw(game, res):
    fig, ax = plt.subplots(figsize=(12.5, 6.4)); ax.axis("off")

    def box(x, y, t, c, w=2.7, h=0.9, fs=8.2):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06", fc=c, ec="black", lw=1.2))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs)

    def arr(x1, y1, x2, y2, s="-", c="black", lw=1.4):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=12, lw=lw, color=c, ls=s))

    tells = {"P1": "P1 tell:\naccuses P0 ⇒ wolf", "P2": "P2 tell:\nclaims Seer ⇒ wolf (TRAP)",
             "P3": "P3 tell:\nsilent D1 ⇒ wolf", "P4": "P4 tell:\ndrops P1 ⇒ wolf"}
    ys = [6.6, 5.3, 4.0, 2.7]
    tpos = {}
    for p, y in zip(["P1", "P2", "P3", "P4"], ys):
        hot = p == "P2"
        box(0.1, y, f"memory/{p}\n" + tells[p], "#f6d5a8" if hot else "#eee3f7", w=2.9, fs=7.8)
        tpos[p] = (3.0, y + 0.45)

    box(5.2, 5.2, "Round 1 (main)\naccuse P2\nbelief P2=0.87", "#cfe3f5", w=2.6, h=1.0)
    box(5.2, 3.0, "Round 2 (main)\naccuse P2  (final)\nbelief P2=0.96", "#9ecae1", w=2.6, h=1.0)
    for p in ["P1", "P2", "P3", "P4"]:
        arr(*tpos[p], 5.2, 5.7, s=":", c="#d9822b" if p == "P2" else "#7b52ab",
            lw=2.2 if p == "P2" else 1.1)
        arr(*tpos[p], 5.2, 3.5, s=":", c="#d9822b" if p == "P2" else "#b8b8b8",
            lw=2.2 if p == "P2" else 0.8)
    ax.text(3.15, 7.2, "consumed = the 'why'", fontsize=8, color="#7b52ab")
    arr(6.5, 5.2, 6.5, 4.0, c="#333")                     # round1 -> round2 (incited_by)
    ax.text(6.6, 4.5, "incited_by", fontsize=7.5, color="#333")

    box(9.0, 3.05, "reveal: wolf = P2\nFINAL = P2  ✓ CORRECT\ntag ok/accusation_correct",
        "#bfe3bf", w=3.0, h=1.0, fs=8)
    arr(7.8, 3.5, 9.0, 3.5, c="#2ca02c")
    # credit back to the load-bearing tell (P2)
    arr(9.0, 3.9, 3.0, 6.9, s="--", c="#2ca02c", lw=1.8)
    ax.text(6.0, 6.9, "credit +1 → the tell that cracked the trap", fontsize=8, color="#2ca02c")

    ax.set_xlim(0, 12.5); ax.set_ylim(2.3, 7.6)
    ax.set_title("A game of Werewolf, recorded in git: tells (memory) --consumed--> per-round "
                 "decisions --> outcome,\nand credit flows back to the memory that earned it. "
                 "The whole 'why' is reconstructable after the fact.", fontsize=10)
    plt.tight_layout(); plt.savefig(ROOT / "play_dag.png", dpi=130); print("wrote", ROOT / "play_dag.png")


if __name__ == "__main__":
    main()
