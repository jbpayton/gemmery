"""Add a 'simulate' step to memory — and watch horizon + model-fidelity decide.

Memory gives you a belief network: hidden state + learned models of your
information sources ("how reliable is this person's tell?"). A REACTIVE agent
acts on its current belief. A PLANNING agent SIMULATES forward — "if I take the
several-step detour to consult that source, my belief will sharpen and then I can
act correctly." This is a classic information-gathering POMDP (heaven/hell with a
priest), the cleanest case where multi-step lookahead provably beats myopia.

Layout: a corridor. A DOOR at one end hides a big reward on one side and a big
penalty on the other (which side is hidden, 50/50). A trusted SOURCE ("priest")
at the other end reveals the answer. Acting immediately is a coin flip. Walking
to the source first costs several steps of no reward, then pays off — so its
value is invisible unless you simulate far enough ahead to see it.

Three things this isolates:
  1. Does simulation help?           reactive/shallow vs deep lookahead
  2. Does deeper help?               sweep the planning horizon h
  3. Does memory fidelity gate it?   the agent's *model* of the source's
                                     reliability (q) may be wrong; a bad model
                                     makes even infinite lookahead useless (or
                                     worse — it deep-plans toward a bad source).
"""

from __future__ import annotations

import random

L = 6            # door at position L
START = 3        # you start here; priest at position 0
STEP_COST = 0.1
WIN, LOSE = 10.0, -10.0
TRUE_RELIABILITY = 0.9   # the source really does tell the truth 90% of the time


def blind_value_model(belief_A: float) -> float:
    """Model value of walking straight to the door and opening the better side."""
    best = max(belief_A, 1 - belief_A)
    return best * WIN + (1 - best) * LOSE


def priest_value_model(pos: int, q: float) -> float:
    """Model value of detour: source -> door -> open, trusting the source at q."""
    after = max(q, 1 - q)                       # modeled post-consult confidence
    reward = after * WIN + (1 - after) * LOSE
    steps = pos + L                             # to priest (pos) then to door (L)
    return reward - STEP_COST * steps


def plan_action(pos, visited, belief_A, h, q):
    """Depth-h receding-horizon choice among the feasible macro-plans."""
    plans = []
    # BLIND: go to door and open (feasible if it fits in h)
    if (L - pos) + 1 <= h:
        plans.append(("door", blind_value_model(belief_A) - STEP_COST * (L - pos)))
    # PRIEST detour (only if not yet consulted and the whole plan fits in h)
    if not visited and (pos + L + 1) <= h:
        plans.append(("priest", priest_value_model(pos, q)))
    if not plans:                               # horizon too short to reach the door
        return +1 if pos < L else "open"        # just advance
    goal = max(plans, key=lambda x: x[1])[0]
    if goal == "priest":
        return -1 if pos > 0 else "consult"
    return +1 if pos < L else "open"


def run_episode(h, q, rng, true_reliability=TRUE_RELIABILITY):
    heaven_A = rng.random() < 0.5               # hidden truth
    pos, visited, belief_A = START, False, 0.5
    steps = 0
    while steps < 50:
        act = plan_action(pos, visited, belief_A, h, q)
        if act == "consult":
            visited = True
            # the REAL source is truthful with `true_reliability`, independent of
            # the agent's (possibly wrong) model q
            says_A = heaven_A if rng.random() < true_reliability else not heaven_A
            belief_A = 1.0 if says_A else 0.0
            continue
        if act == "open":
            correct = (belief_A >= 0.5) == heaven_A
            return (WIN if correct else LOSE) - STEP_COST * steps
        pos += act
        steps += 1
    return -STEP_COST * steps


HORIZONS = [4, 6, 8, 10, 12, 14]


def sweep(q, true_reliability, episodes=5000):
    out = {}
    for h in HORIZONS:
        rng = random.Random(1234 + h)
        out[h] = sum(run_episode(h, q, rng, true_reliability) for _ in range(episodes)) / episodes
    return out


if __name__ == "__main__":
    print(f"corridor: start={START}, door={L}, source at 0. The source detour needs "
          f"~{START + L + 1} steps of lookahead before its payoff is visible.\n")
    good = sweep(0.9, 0.9)     # accurate model of a reliable source
    bad = sweep(0.52, 0.9)     # under-trust: model thinks the source ~= a coin
    overtrust = sweep(0.9, 0.5)  # over-trust: model says reliable, source is a coin
    print("expected reward vs planning horizon (acting blind ≈ 0):")
    print(f"{'horizon':>8} | {'good model':>11} | {'under-trust':>11} | {'over-trust':>11}")
    for h in HORIZONS:
        print(f"{h:>8} | {good[h]:>11.2f} | {bad[h]:>11.2f} | {overtrust[h]:>11.2f}")
