# Branching predictive realities — forked futures, explored, diffed, chosen

**The gap this fills.** We'd asserted "branches = alternate realities" but never
*used* them as such: the integrated experiment created plan branches without
exploring them; the simulate experiment rolled futures forward with no git. This
experiment does the full move on the played Werewolf game (wolf = P2, the
fake-Seer trap, using the focal's actual captured Round-1 belief): **fork one
real branch per candidate decision, simulate each future into its branch,
inhabit each blind, diff them, select, execute, then explain the roads not
taken from the record.**

## The apparatus (all real `GitStore` operations)

1. The game gains a consequential move: P0's Day-1 vote is decisive (vote the
   wolf → clean win 1.0; miss → lose an innocent + a night freeze → Day-2 catch
   scores 0.6, miss scores 0).
2. For each candidate vote v: `branch_frontier("future/vote-v")`, then capture
   INTO the branch a **plan gem** and a **rollout gem** — the simulated timeline
   under every wolf-hypothesis, weighted by the belief; EV computed mechanically.
   `EV: vote-P2 0.906 · vote-P1 0.598 · vote-P4 0.588 · vote-P3 0.582.`
3. **Four sub-agents each inhabit ONE branch**, blind to the others, and argue
   "why WOULD a reasonable P0 take this path" from inside it. Assessments are
   captured as gems on their branches.
4. `git diff` between two branch tips = the **computed marginal consequence**
   of one decision over another (each future's plan/rollout/assessment files
   appear and disappear across the diff).
5. `select_to_main(vote-P2)`; execute the truth (the wolf WAS P2 → win, Day 1,
   no losses); tag + signed success; **credit the roads not taken by their EV
   gap** (−0.31 … −0.32) — the rejected futures now carry their opportunity
   cost as valuation.

## Results

- **Blind convergence.** The four inhabitants, each seeing only their own
  future, independently produced the correct portfolio ranking:
  `P2 = ENDORSE (0.87) · P3 = CAUTION · P1, P4 = REJECT` — matching the
  mechanical EVs they never saw compared.
- **The counterfactual explainer works.** A final agent, given only the git
  record, produced a three-part analysis (`out/explanation.md`): why we chose
  vote-P2; **why we *would* have chosen vote-P1 and what its future held**
  ("lynch an almost-certainly-innocent 96% of the time, silence the one player
  pointing at our top suspect, hand P2 a free night… trades a clean Day-1 win
  for a casualty-laden late catch"); and what the apparatus bought — its own
  summary is the thesis:

  > "Because each rejected future persists in git with its own advocate's best
  > case, we can verify after the reveal that the decision was right **for the
  > right reasons — not merely lucky** — and reuse the same apparatus when the
  > next decision's belief mass is less mercifully concentrated."

- **The state quartet, now fully demonstrated:** *was* (checkout the pre-fork
  situation), ***if*** (four live futures on branches), *delta* (diff between
  futures = marginal consequence), *why* (plans, rollouts, inhabitant cases,
  consumed edges, and EV-gap credit on the rejected branches).

## Honest scope

The rollouts are mechanical simulations of a small rule-driven game, and the
belief was mercifully concentrated (P2 = 0.87) so the selection wasn't close;
the point demonstrated is the **apparatus** — cheap forkable world-state,
blind per-branch advocacy, computed diffs, opportunity-cost credit, and
post-hoc counterfactual explanation — not a hard decision problem. The natural
stress test is a decision with genuinely competitive futures (belief spread
flat), where the portfolio comparison has to earn the choice.

Reproduce: `python experiments/futures/build.py` → run the four inhabitant
agents → `python experiments/futures/choose.py` → explainer agent → `plot.py`.
(Amusing footnote: the selection script was originally `select.py`, which
shadowed the stdlib module `subprocess` needs — renamed `choose.py`.)
