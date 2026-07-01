"""Complex, noisy behavioral rules — where similarity beats exact aggregation.

A person whose behavior is a *simple* tell ("P2 always fakes Doctor") is a
lookup. A person whose behavior follows a **complex, noisy rule** — a non-linear
function of several interacting situational features, obeyed most of the time but
not always — is a *learning* problem: to predict them you must infer the rule
from many examples across many situations and see through the deviations.

This is the mirror image of the exact-aggregate result. There the query was a
dense count and the structured index won. Here the query is "what will this
person do in THIS situation?", the context is high-dimensional, so an *exact*
conditional lookup lands in an empty/near-empty cell, while *similarity*
retrieval (kNN over past situations) generalizes across nearby cells and
approaches the Bayes ceiling. Different query, different right tool.

Each persona's rule: a random weighted sum of context features PLUS a few
pairwise interactions (so it is genuinely non-linear / not a single tell),
thresholded, then flipped with probability = noise (the "doesn't always" part).
"""

from __future__ import annotations

import numpy as np

N_FEATURES = 12
N_INTERACTIONS = 5
NOISE = 0.15
M_HISTORY = 2500     # games of history per persona
T_TEST = 600
K_NN = 40


def make_rule(seed: int, nf: int = N_FEATURES):
    r = np.random.RandomState(seed)
    w = r.randn(nf)
    inter = [(r.randint(nf), r.randint(nf), r.randn() * 2.0)
             for _ in range(N_INTERACTIONS)]
    # threshold at the median score of random contexts, so classes are balanced
    sample = r.randint(0, 2, size=(4000, nf))
    scores = sample @ w + sum(v * sample[:, i] * sample[:, j] for i, j, v in inter)
    theta = float(np.median(scores))

    def rule(x):
        s = x @ w + sum(v * x[i] * x[j] for i, j, v in inter)
        return int(s > theta)
    return rule


def sample_data(rule, m, noise, seed, nf: int = N_FEATURES):
    r = np.random.RandomState(seed)
    X = r.randint(0, 2, size=(m, nf))
    y_true = np.array([rule(x) for x in X])
    y = y_true ^ (r.rand(m) < noise).astype(int)   # obeyed most of the time
    return X, y


# --------------------------------------------------------------------------- #
# Predictors = memory-access strategies
# --------------------------------------------------------------------------- #
def base_rate(Xtr, ytr, x):
    """Marginal: this person's overall behavior, ignoring the situation."""
    return int(ytr.mean() > 0.5)


def exact_cell(Xtr, ytr, x):
    """Structured EXACT conditional: past games with the identical situation.
    In a high-dim context most cells are empty -> falls back to base rate."""
    mask = np.all(Xtr == x, axis=1)
    if mask.any():
        return int(ytr[mask].mean() > 0.5)
    return int(ytr.mean() > 0.5)


def knn(Xtr, ytr, x, k=K_NN):
    """Similarity (kNN over situations): the k most similar past situations,
    majority behavior. Generalizes across nearby cells."""
    d = np.sum(Xtr != x, axis=1)          # Hamming distance
    idx = np.argpartition(d, k)[:k]
    return int(ytr[idx].mean() > 0.5)


def evaluate(seed=0, nf=N_FEATURES):
    rule = make_rule(1000 + seed, nf)
    Xtr, ytr = sample_data(rule, M_HISTORY, NOISE, seed=seed, nf=nf)
    Xte, yte = sample_data(rule, T_TEST, NOISE, seed=seed + 777, nf=nf)

    def acc(fn):
        return float(np.mean([fn(Xtr, ytr, x) == yte[i] for i, x in enumerate(Xte)]))

    bayes = float(np.mean([rule(x) == yte[i] for i, x in enumerate(Xte)]))
    # avg cell occupancy for the test contexts
    occ = np.mean([np.all(Xtr == x, axis=1).sum() for x in Xte[:200]])
    return {
        "bayes_ceiling": bayes,
        "base_rate_marginal": acc(base_rate),
        "exact_cell_conditional": acc(exact_cell),
        "knn_similarity": acc(knn),
        "avg_exact_cell_samples": float(occ),
    }


if __name__ == "__main__":
    # average over several personas for stability
    keys = ["bayes_ceiling", "base_rate_marginal", "exact_cell_conditional",
            "knn_similarity", "avg_exact_cell_samples"]
    agg = {k: [] for k in keys}
    for s in range(8):
        r = evaluate(s)
        for k in keys:
            agg[k].append(r[k])
    print(f"{N_FEATURES} features -> {2**N_FEATURES:,} possible situations; "
          f"{M_HISTORY:,} games of history per persona")
    print(f"avg samples in the EXACT current-situation cell: "
          f"{np.mean(agg['avg_exact_cell_samples']):.2f}\n")
    print(f"predict the person's next move (noise={NOISE}, so Bayes ceiling ~{1-NOISE:.2f}):")
    for k in ["base_rate_marginal", "exact_cell_conditional", "knn_similarity",
              "bayes_ceiling"]:
        print(f"  {k:26s}: {np.mean(agg[k]):.3f}")
