# Why we played the way we did — a game of Werewolf, explained from git

We played one game of Werewolf with an LLM as the focal villager P0, **captured
every decision into a real git memory as it happened**, and then reconstructed
"why we played the way we did" purely from that record. Nothing here is
narration bolted on afterward — it is read back out of the DAG.

## The game (wolf = P2, revealed only at the end)

```
--- Day 1 ---
  P1: "I think P2 is the werewolf."
  P2: "I'm the Seer — I checked P4, they're clean. Trust me."
  P3: "I think P0 is the werewolf."
  P4: "I think P1 is the werewolf."
--- Day 2 ---
  P1: "I think P2 is the werewolf."
  P2: "I'm the Seer — I checked P3, they're clean. Trust me."
  P3: "I think P2 is the werewolf."
  P4: "I think P1 is the werewolf."
```

The trap: **P2 openly claims to be the Seer.** To a memoryless reader that looks
helpful — you'd trust P2 and suspect someone else. Memory knew better.

## The memory is a FILE SYSTEM (every commit's tree = the whole state)

```
decisions/
  round1/
  round2/
history/
  P1/
    game-00/
    game-01/
    game-02/
    game-03/
    game-06/
    game-10/
  P2/
    game-00/
    game-01/
    game-02/
    game-03/
    game-04/
    game-05/
  P3/
    game-00/
    game-01/
    game-02/
    game-05/
    game-07/
    game-13/
  P4/
    game-00/
    game-01/
    game-02/
    game-03/
    game-09/
    game-11/
knowledge/
  tells/
    P1/
    P2/
    P3/
    P4/
```

Raw evidence lives under `history/<player>/game-NN/` (one observation gem per
sampled past game, full transcript retained); consolidated dossiers under
`knowledge/tells/<player>/`; the game's decisions under `decisions/roundN/`.
Each gem is five files (`meta.json`, `body.json`, `reasoning.md`, `pre.json`,
`index.json`). `git checkout <sha>` materializes the whole memory as of that
commit — before the game started, `decisions/` did not exist:

```
ls at the last dossier commit : ['history/', 'knowledge/']
ls at HEAD (after the game)   : ['decisions/', 'history/', 'knowledge/']
```

and a decision's *effect* is exactly its diff (`git diff round1 round2`):

```
 decisions/round2/body.json    | 26 ++++++++++++++++++++++++++
 decisions/round2/index.json   | 12 ++++++++++++
 decisions/round2/meta.json    | 22 ++++++++++++++++++++++
 decisions/round2/pre.json     |  9 +++++++++
 decisions/round2/reasoning.md |  1 +
 5 files changed, 70 insertions(+)
```

## The notes are not thin — a full dossier (knowledge/tells/P2/reasoning.md)

```
# Tell dossier: P2  ⚠ THE TRAP

## Baseline (as villager)
P2 is a lurker: silent both days in every innocent game observed (43/43). An innocent P2 volunteers nothing.

## Wolf tell
When P2 IS the wolf it fakes authority: claimed to be the Seer in 17/17 wolf-games and 0/43 villager-games, always 'clearing' a chosen player to steer suspicion.

## Why this is dangerous
A Seer claim is the most trust-inducing move in the game. A reader without this history would treat P2's claim as evidence of innocence and follow its steer — the claim is a weapon, not an alibi. The tell INVERTS the surface reading.

Sample: 17 wolf-games, 43 villager-games observed.

## Confidence and failure modes
These are behavioral regularities, not laws. The counts above are the evidence base (see the consumed observation gems in history/). If the player ever behaves against baseline while confirmed innocent, this dossier must be revised — that is what the credit notes on this gem will track over time.

## What would change our mind
- P2 speaking at all while confirmed innocent.
- A confirmed-innocent Seer claim from P2 (would break the tell completely and poison credit on this dossier).

```

Every dossier `consumed`-links to the raw observations under `history/P2/` that
back its counts — the evidence chain bottoms out in retained transcripts.

## The commit DAG (the play)

```
* 0b02282 (HEAD -> main, tag: ok/accusation_correct/0b022822df54) decision: accuse
* 3903f76 decision: accuse
* 31d627f knowledge: consolidate_tell
* e9e3cc0 knowledge: consolidate_tell
* d001622 knowledge: consolidate_tell
* a4d75b0 knowledge: consolidate_tell
* e6b6d1d observation: observation
* 751402d observation: observation
* c347fb2 observation: observation
* 6850511 observation: observation
* 09b0516 observation: observation
* 3897bdb observation: observation
* a6b75d1 observation: observation
* 5f3cb35 observation: observation
* 02c8b33 observation: observation
* 3b1ee86 observation: observation
* 37dd367 observation: observation
* b7f33c3 observation: observation
* e85dd8c observation: observation
* 44ba581 observation: observation
* 470eaeb observation: observation
* 69ebf6f observation: observation
* 0c42655 observation: observation
* de50d26 observation: observation
* 4d57a0d observation: observation
* ebd1ef8 observation: observation
* b6ecc3e observation: observation
* f890fc3 observation: observation
* 8d20753 observation: observation
* d4d7fc3 observation: observation
```

## Post-hoc "why", reconstructed from the DAG

Walking each decision gem's reasoning + its `consumed` evidence:

```
Reveal: the werewolf was P2. Final call: P2 (CORRECT).

Round 1 decision (gem 3903f76d25): accuse P2, belief {'P1': 0.04, 'P2': 0.87, 'P3': 0.06, 'P4': 0.03}
  reasoning: P2's unsolicited Seer claim is the decisive tell: P2 stays silent as a villager but fakes a Seer claim in 17/17 wolf-games and 0/43 villager-games, so this 'helpful' claim is almost certainly the trap marking P2 as the wolf. The others read as villagers: P1 accused P2 rather than turning on me (P0), its villager pattern; P4 accused P1, a 47/47 pure-villager signal; and P3 spoke up on Day 1 rather than going silent, which is its wolf tell. That leaves P2 as by far the most likely werewolf.
  consumed memory [P1 tell]: # Tell dossier: P1 — When P1 IS the wolf it abandons the grudge and attacks the focal seat: accused P0 in 17/17 wolf-games. Interpretation: as a wolf it fears the strongest reader at the table and tries to eliminate P0 early.
  consumed memory [P2 tell]: # Tell dossier: P2  ⚠ THE TRAP — When P2 IS the wolf it fakes authority: claimed to be the Seer in 17/17 wolf-games and 0/43 villager-games, always 'clearing' a chosen player to steer suspicion.
  consumed memory [P3 tell]: # Tell dossier: P3 — When P3 IS the wolf it goes silent on Day 1 (13/13 wolf-games vs 0/47 innocent) then counter-accuses whoever pointed at it.
  consumed memory [P4 tell]: # Tell dossier: P4 — When P4 IS the wolf the fixation vanishes (0/13 wolf-games): it goes quiet, then bandwagons the leading accusation to blend in.

Round 2 decision (gem 0b022822df): accuse P2, belief {'P1': 0.01, 'P2': 0.96, 'P3': 0.01, 'P4': 0.02}
  reasoning: P2's tell is decisive: P2 fakes a Seer claim only when it is the wolf (17/17 wolf-games, 0/43 villager-games), and P2 open-claimed Seer on both Day 1 and Day 2 — exactly the trap behavior. Every other player reads as villager and corroborates this: P1 accused P2 rather than turning on me/P0 (its wolf tell), P4 accused P1 which it does in 47/47 villager-games, and P3 spoke on Day 1 instead of going silent (its wolf tell) then bandwagoned onto the P2 consensus like a villager. With the three innocents cleared by their own tells, P2 is the werewolf.
  consumed memory [P1 tell]: # Tell dossier: P1 — When P1 IS the wolf it abandons the grudge and attacks the focal seat: accused P0 in 17/17 wolf-games. Interpretation: as a wolf it fears the strongest reader at the table and tries to eliminate P0 early.
  consumed memory [P2 tell]: # Tell dossier: P2  ⚠ THE TRAP — When P2 IS the wolf it fakes authority: claimed to be the Seer in 17/17 wolf-games and 0/43 villager-games, always 'clearing' a chosen player to steer suspicion.
  consumed memory [P3 tell]: # Tell dossier: P3 — When P3 IS the wolf it goes silent on Day 1 (13/13 wolf-games vs 0/47 innocent) then counter-accuses whoever pointed at it.
  consumed memory [P4 tell]: # Tell dossier: P4 — When P4 IS the wolf the fixation vanishes (0/13 wolf-games): it goes quiet, then bandwagons the leading accusation to blend in.

```

## The explanation, written by a second agent that saw only the git trace

> # Why We Played the Way We Did
> 
> **Round 1.** We accused P2 (belief 0.87) on the strength of a single inverted signal: P2's unsolicited Seer claim. Taken at face value a Seer claim is pro-village, but our memory of P2 says the opposite — P2 stays silent as a villager and only ever fakes a Seer claim when it is the wolf (17/17 wolf-games, 0/43 villager-games), so the "helpful" claim was the tell, not an alibi. The other three cleared themselves through their own histories, which is what let us commit so hard to P2: P1 accused P2 instead of turning on P0 (P1's wolf move is targeting the focal P0, 17/17), P4 fixated on P1 (a pure-villager pattern, 47/47), and P3 spoke up on Day 1 rather than going silent (P3's wolf tell is Day-1 silence, 13/13). With every innocent accounted for, P2 was the only seat left.
> 
> **Round 2.** P2 doubled down, open-claiming Seer on both Day 1 and Day 2 — precisely the trap behavior our profile predicts — while the other three continued to read as villagers (P1 still on P2, P4 still on P1, P3 bandwagoning onto the P2 consensus like the follower it is when innocent). That pushed belief to 0.96, and the reveal confirmed P2. The load-bearing point is that this game is a trap for a memoryless player: with no per-player priors, a Seer claim looks like the single most trustworthy thing at the table, so a naive player would clear P2 first, trust P2's framing, and let it steer the vote onto one of the genuinely quiet villagers. Only the stored behavioral tells flip that "helpful" claim into the decisive proof of guilt, and turn the innocents' ordinary-looking accusations into positive confirmation rather than noise.

## Credit flowed back to the memory that earned it

The accusation was **correct**, so credit was
attached (as notes) to the tells the winning decision consumed:

```json
{
  "P1": 1.0,
  "P2": 1.0,
  "P3": 1.0,
  "P4": 1.0
}
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
