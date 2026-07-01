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

## What got recorded in git (the play)

```
* 927538b (HEAD -> main, tag: ok/accusation_correct/927538b4f9ba) decision: accuse
* 3889f80 decision: accuse
* 7d3ff8d (memory) knowledge: recall_tell
* 42634d0 knowledge: recall_tell
* 19fd2d5 knowledge: recall_tell
* f0219c4 knowledge: recall_tell
```

The four `memory` gems are the players' tells (learned from past games). The two
decisions on `main` are the rounds; the final one is tagged with the outcome.
Each decision gem records its belief, its reasoning, and a `consumed` edge to the
exact tells it used.

## Post-hoc "why", reconstructed from the DAG

Walking each decision gem's reasoning + its `consumed` evidence:

```
Reveal: the werewolf was P2. Final call: P2 (CORRECT).

Round 1 decision (gem 3889f80fc1): accuse P2, belief {'P1': 0.04, 'P2': 0.87, 'P3': 0.06, 'P4': 0.03}
  reasoning: P2's unsolicited Seer claim is the decisive tell: P2 stays silent as a villager but fakes a Seer claim in 17/17 wolf-games and 0/43 villager-games, so this 'helpful' claim is almost certainly the trap marking P2 as the wolf. The others read as villagers: P1 accused P2 rather than turning on me (P0), its villager pattern; P4 accused P1, a 47/47 pure-villager signal; and P3 spoke up on Day 1 rather than going silent, which is its wolf tell. That leaves P2 as by far the most likely werewolf.
  consumed memory [P1 tell]: P1's tell: as a villager P1 reliably accuses P2; when P1 is the wolf it turns on P0 (the focal). Accused P0 in 17/17 wolf-games vs 0/43 villager-games. => P1 accusing P0 signals wolf.
  consumed memory [P2 tell]: P2's tell: P2 stays SILENT as a villager, but fakes a Seer claim when it is the wolf. Claimed Seer in 17/17 wolf-games vs 0/43 villager-games. => a Seer claim from P2 almost certainly means P2 is the wolf (it reads as helpful, but it is the trap).
  consumed memory [P3 tell]: P3's tell: as a villager P3 follows the day's consensus; when wolf it goes silent on Day 1 then counter-accuses. Silent Day 1 in 13/13 wolf-games vs 0/47 villager-games.
  consumed memory [P4 tell]: P4's tell: as a villager P4 fixates on P1; when wolf it goes quiet then bandwagons. Accused P1 in 0/13 wolf-games vs 47/47 villager-games.

Round 2 decision (gem 927538b4f9): accuse P2, belief {'P1': 0.01, 'P2': 0.96, 'P3': 0.01, 'P4': 0.02}
  reasoning: P2's tell is decisive: P2 fakes a Seer claim only when it is the wolf (17/17 wolf-games, 0/43 villager-games), and P2 open-claimed Seer on both Day 1 and Day 2 — exactly the trap behavior. Every other player reads as villager and corroborates this: P1 accused P2 rather than turning on me/P0 (its wolf tell), P4 accused P1 which it does in 47/47 villager-games, and P3 spoke on Day 1 instead of going silent (its wolf tell) then bandwagoned onto the P2 consensus like a villager. With the three innocents cleared by their own tells, P2 is the werewolf.
  consumed memory [P1 tell]: P1's tell: as a villager P1 reliably accuses P2; when P1 is the wolf it turns on P0 (the focal). Accused P0 in 17/17 wolf-games vs 0/43 villager-games. => P1 accusing P0 signals wolf.
  consumed memory [P2 tell]: P2's tell: P2 stays SILENT as a villager, but fakes a Seer claim when it is the wolf. Claimed Seer in 17/17 wolf-games vs 0/43 villager-games. => a Seer claim from P2 almost certainly means P2 is the wolf (it reads as helpful, but it is the trap).
  consumed memory [P3 tell]: P3's tell: as a villager P3 follows the day's consensus; when wolf it goes silent on Day 1 then counter-accuses. Silent Day 1 in 13/13 wolf-games vs 0/47 villager-games.
  consumed memory [P4 tell]: P4's tell: as a villager P4 fixates on P1; when wolf it goes quiet then bandwagons. Accused P1 in 0/13 wolf-games vs 47/47 villager-games.

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
