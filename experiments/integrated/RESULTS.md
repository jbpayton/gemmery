# The integrated test — git memory serving a plan, hypotheses tracked in git

This is the end-to-end loop the rest of the repo built piece by piece but never
ran together: **git memory serves the model a simulation plans over, the
hypotheses are captured as gems in git, and it's compared against
vanilla-markdown-served and no-memory planning.** It is deliberately set in the
regime where the earlier findings *stack* into a decisive result.

## Task

Advisors' reliability **drifts** over a long career (some were great and have
gone bad; some have come good). To plan well you need each advisor's **current**
reliability — a recency-filtered aggregate over 320,000 records (a naive context
read holds ~1.6%). Then you commit to a **multi-step** plan that relies on your
chosen advisor; reward = P(all T steps succeed) = current_reliability(pick)^T.

## Part 1 — git-served vs markdown-served vs no-memory (`integrated_plan.png`)

| plan length T | no memory | markdown-served | git-served (Gemmery) |
|---|---|---|---|
| 1 | 0.500 | 0.384 | **0.889** |
| 2 | 0.250 | 0.147 | **0.791** |
| 4 | 0.062 | 0.022 | **0.626** |
| 6 | 0.016 | 0.003 | **0.495** |
| 8 | 0.004 | 0.000 | **0.392** |

- **git** does a recency-filtered exact aggregate → picks the *currently* best
  advisor (A7, current reliability 0.89) → plans well.
- **markdown** naively reads the slice that fits context — the *oldest* records at
  the top of the file — and **over-trusts a fallen advisor** (A4: 0.87 back then,
  **0.38 now**). Its model is confidently wrong.
- The consequence is the punchline of the whole investigation: **markdown-served
  planning is *below* no-memory at every horizon**, because a miscalibrated model
  makes multi-step planning worse than none (the `simulate` finding), and the gap
  **amplifies with plan length** as the model error compounds.

This is the conjunction: **recency-filtered exact aggregation** (only the
structured index can do it at scale — the `scale` finding) **× a bad model makes
deep plans worse than none** (the `simulate` finding) ⇒ git-served planning beats
both baselines, decisively and by a margin that grows with horizon.

## Part 2 — hypotheses tracked in git (`git_plan_tracking.py`)

The DAG is used as the plan-search tree, concretely (real `GitStore`):

```
hypotheses (each a frontier branch):
  frontier/plan/A7/0  -> rely on A7  (simulated value 0.876)
  frontier/plan/A1/0  -> rely on A1  (simulated value 0.868)
  ... one branch per candidate plan ...
selected to main: rely on A7        # cherry-pick the winner
executed 6-step plan -> success; credit note on main gem: 0.495
```

Every candidate plan is an immutable gem on its own `frontier/plan/*` branch
(the simulated hypotheses); the chosen one is cherry-picked to `main` (selection
over merge, §1.7); the outcome is a signed success + credit **note** (immutable
record, mutable valuation, §1.1). Frontier branches are retained for later
synthesis. That is the design's claim — *the DAG is the search tree, credit is
backed-up value* — made literal and runnable, not just asserted.

## So: where are we?

Previously: **no.** Each earlier experiment isolated one piece — git served
*retrieval*, and the `simulate` experiment planned over a bare model with no git.
**Now: yes.** git memory serves the planning model *and* records the hypotheses,
and it beats both markdown-served planning (which is worse than no memory here)
and no memory — with the advantage growing as you plan further ahead.

Reproduce: `python experiments/integrated/integrated_demo.py`,
`python experiments/integrated/git_plan_tracking.py`,
`.venv/bin/python experiments/integrated/plot.py`.
