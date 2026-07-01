# The 'simulate' step — memory as a belief network you plan over

Every earlier experiment used memory *reactively* (retrieve / predict one step).
This one adds the step you proposed: **simulate the memory-learned models forward
and plan.** It tests three things at once — does simulation help, does deeper
help, and does the quality of the memory-model gate it.

## Setup (an information-gathering POMDP — heaven/hell with a priest)

A corridor. A **door** at one end hides a big reward on one side and a big penalty
on the other; which side is hidden (50/50). A **source** ("priest") at the other
end reveals the answer. Acting immediately is a coin flip (≈ 0). Walking to the
source first costs several steps of *no* reward, then pays off — so its value is
**invisible unless you simulate far enough ahead to see it.** The source's
reliability is exactly the kind of thing memory estimates ("how much is this
person's tell worth?"); the agent plans with its *model* `q` of that reliability,
which may be wrong.

## Result (expected reward vs planning horizon; acting blind ≈ 0)

| horizon (steps simulated) | good model (q≈truth) | under-trust (q≈0.5) | over-trust (model wrong) |
|---|---|---|---|
| 4 – 8 | −0.3 | −0.3 | −0.3 |
| **10 – 14** | **+7.1** | −0.2 | **−1.0** |

The source round-trip needs ~10 steps of lookahead. Below it, all strategies are
stuck at the blind coin-flip. `simulate_horizon.png` shows the curves.

Three findings, matching the hypothesis:

1. **Simulation helps — a lot** (+7.1 vs ≈0), *once the horizon is deep enough.*
2. **Deeper helps, with a hard threshold.** The payoff is literally "multiple
   steps into the future": reward is flat until horizon crosses the length of the
   multi-step detour (~10), then jumps. A one- or few-step lookahead sees nothing.
3. **Memory fidelity gates it, both ways:**
   - *Under-trust* — if the model wrongly thinks the source is ~useless, the agent
     never takes the detour, so even infinite lookahead buys nothing (flat ≈ 0).
   - *Over-trust* — if the model says the source is reliable but it's actually a
     coin, deep planning marches to the source, trusts its garbage, and ends up
     **worse than acting blind** (−1.0). Deep simulation over a bad model doesn't
     just waste effort; it actively misleads.

## Why this matters for Gemmery

This is the memory→planning bridge, and it's native to the substrate: the DAG is
the search tree (`frontier/*` = simulated futures, cherry-pick-to-`main` =
selection), **credit is the backed-up rollout value**, and the reversible
deliberation sub-DAG is the zone you can simulate in safely; a simulation is
itself a gem, so real outcomes later *recalibrate* the model. The experiment also
sharpens the design imperative from the memory experiments: because deep
simulation over a bad model is *worse than none*, the model you simulate must be
**grounded and calibrated** — which is exactly what test-bound, earned credit
(§7) provides (a source's weight is its track record, not its storage-time
confidence). Memory quality doesn't just help planning; past a horizon it
*determines whether planning helps or harms.*

(Mechanical Monte-Carlo — no LLM; the 'simulate' step rolls the learned model
forward. Reproduce: `python experiments/simulate/simulate_demo.py`,
`.venv/bin/python experiments/simulate/plot.py`.)
