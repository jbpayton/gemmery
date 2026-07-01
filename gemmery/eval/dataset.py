"""Phase-0 dataset + the decorrelation feasibility question (spec §10.2).

The whole experiment hinges on one constructible-or-not question: can we build
task pairs that **decorrelate problem-surface similarity from solution-schema
similarity**, and populate the cell GitOfThoughts binned away — *low* problem
similarity, *high* solution similarity (method transfer)?  If surface and method
covary too hard to separate, the experiment can't run, and that itself is a
finding (spec §14.4).

Construction strategy: pick a handful of **solution schemas** (methods), and
instantiate each across deliberately diverse **surface domains** so that two
tasks sharing a method share almost no surface vocabulary.  Add same-surface /
different-method distractors (the answer-copy cell).  Then *measure*:

* ``problem_sim`` = cosine(embed(problem_text_a), embed(problem_text_b))   — surface
* ``solution_sim`` = cosine(embed(solution_sketch_a), solution_sketch_b)   — method

and check (a) the target cell is populated and (b) the two similarities don't
covary so tightly you can't separate them.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from ..index.embedder import Embedder, default_embedder


@dataclass
class Verifier:
    """A cheap automatic test — the bound ``test`` (Invariant 2).

    ``entry_point`` is the function name the solver must define; ``cases`` are
    ``(args, expected)`` pairs.  ``canonical_solution`` is reference code (used by
    the simulated solver and to sanity-check the verifier itself).
    """

    entry_point: str
    cases: list[tuple]
    canonical_solution: str = ""

    @property
    def test_id(self) -> str:
        return f"unit::{self.entry_point}"


@dataclass
class Task:
    id: str
    schema_id: str  # the solution schema (method) — the transfer-relevant label
    surface_domain: str  # the surface vocabulary domain
    problem_text: str  # surface description (what varies across instances)
    solution_sketch: str  # canonical method shape (what's shared within a schema)
    verifier: Optional[Verifier] = None


# --------------------------------------------------------------------------- #
# Solution schemas (methods).  Each sketch is the *shape* of the fix; tasks that
# share a schema share this shape even across wildly different surfaces.
# --------------------------------------------------------------------------- #
SCHEMAS = {
    "memoize": "Wrap a pure expensive function f(x): keep a cache dict; if x in "
               "cache return cache[x], else compute f(x), store, and return it.",
    "retry_backoff": "Wrap an idempotent flaky operation in a loop: on failure, "
                     "sleep an exponentially growing delay with jitter and retry "
                     "up to N times; raise if exhausted.",
    "index_lookup": "Replace a repeated linear scan over a collection with a "
                    "precomputed dict keyed by the lookup attribute, turning an "
                    "O(n) search per query into an O(1) dict access.",
    "batch_dedup": "Collapse N repeated per-item calls inside a loop into one "
                   "batched call over the unique keys, then map results back.",
    "guard_clause": "Flatten deeply nested conditionals by returning early for "
                    "edge/invalid cases at the top, leaving the main path "
                    "unindented.",
    "accumulator": "Replace repeated quadratic concatenation in a loop with an "
                   "accumulator list appended each iteration and joined once at "
                   "the end.",
}


def _realize(schema: str, domain: str) -> str:
    """A small per-instance realization clause.

    Real solution write-ups are *similar but not identical* within a method and
    mention a little domain context.  Appending one neutral, mildly
    domain-flavored clause keeps within-schema solution-similarity high but below
    a synthetic 1.000, and injects the realistic surface-leakage that makes the
    decorrelation test honest rather than rigged.
    """
    return f"In this instance the method is realized in the {domain} domain."


def _t(id, schema, domain, problem, verifier=None) -> Task:
    sketch = SCHEMAS[schema] + " " + _realize(schema, domain)
    return Task(id=id, schema_id=schema, surface_domain=domain,
                problem_text=problem, solution_sketch=sketch,
                verifier=verifier)


# --------------------------------------------------------------------------- #
# The dataset: each schema instantiated across 4 diverse surface domains.
# Problem texts are intentionally domain-loaded so within-schema surface overlap
# is low.  A representative subset carries runnable verifiers.
# --------------------------------------------------------------------------- #
def build_dataset() -> list[Task]:
    tasks: list[Task] = []

    # --- memoize across surfaces -------------------------------------- #
    tasks += [
        _t("memo_game", "memoize", "gamedev",
           "Every frame the enemy AI recomputes the same A* pathfinding "
           "heuristic for a battle grid that almost never changes, so the "
           "game stutters during combat.",
           Verifier("cached_heuristic",
                    [((("a",),), 1), ((("a",),), 1), ((("b",),), 1)],
                    "def cached_heuristic(state, _c={}):\n"
                    "    if state in _c: return _c[state]\n"
                    "    _c[state] = 1\n    return _c[state]")),
        _t("memo_fin", "memoize", "finance",
           "A risk dashboard recalculates the identical portfolio Value-at-Risk "
           "for the same holdings on every widget refresh, making the trading "
           "screen lag."),
        _t("memo_bio", "memoize", "bioinformatics",
           "A genome aligner recomputes the alignment score matrix for read "
           "pairs it has already scored, so the overnight batch never finishes "
           "in time."),
        _t("memo_web", "memoize", "web",
           "An HTTP endpoint re-renders the same Markdown knowledge-base article "
           "from source on every page view, driving tail latency up."),
    ]

    # --- retry_backoff across surfaces -------------------------------- #
    tasks += [
        _t("retry_pay", "retry_backoff", "payments",
           "Charging a card sometimes fails with a transient gateway timeout; "
           "the idempotent capture should be retried with backoff instead of "
           "erroring out the checkout. Write `robust_capture()` that returns 'ok' "
           "despite an underlying call that fails the first time.",
           Verifier("robust_capture",
                    [((), "ok")],
                    "def robust_capture():\n"
                    "    calls = {'n': 0}\n"
                    "    def attempt():\n"
                    "        calls['n'] += 1\n"
                    "        if calls['n'] < 2: raise IOError('timeout')\n"
                    "        return 'ok'\n"
                    "    delay = 1\n"
                    "    for _ in range(5):\n"
                    "        try:\n"
                    "            return attempt()\n"
                    "        except IOError:\n"
                    "            delay *= 2  # exponential backoff\n"
                    "    raise RuntimeError('retries exhausted')")),
        _t("retry_iot", "retry_backoff", "iot",
           "A sensor gateway intermittently drops the MQTT publish under radio "
           "interference; the idempotent telemetry push should back off and try "
           "again rather than losing the reading."),
        _t("retry_ci", "retry_backoff", "devops",
           "A CI step that pulls a base image occasionally hits a flaky registry "
           "503; the idempotent pull should be retried with growing delay before "
           "the build is failed."),
        _t("retry_db", "retry_backoff", "database",
           "Under failover a write occasionally returns a transient 'not leader' "
           "error; the idempotent upsert should retry on a backoff until the new "
           "primary accepts it."),
    ]

    # --- index_lookup across surfaces --------------------------------- #
    tasks += [
        _t("idx_ecom", "index_lookup", "ecommerce",
           "Rendering a cart re-scans the whole product list to find each line "
           "item's price, so big carts on the catalog page crawl.",
           Verifier("price_of",
                    [(("p2", [("p1", 10), ("p2", 20)]), 20)],
                    "def price_of(pid, products):\n"
                    "    idx = {k: v for k, v in products}\n"
                    "    return idx[pid]")),
        _t("idx_geo", "index_lookup", "geospatial",
           "A routing service loops over every road segment to find the one "
           "matching an OSM id for each turn, so route assembly is quadratic."),
        _t("idx_lint", "index_lookup", "compilers",
           "A linter walks the entire symbol list to resolve each identifier "
           "reference, making analysis of large files painfully slow."),
        _t("idx_hr", "index_lookup", "hr-software",
           "A payroll run searches the full employee array to look up each "
           "person's tax band by id on every paycheck, blowing the batch window."),
    ]

    # --- batch_dedup across surfaces ---------------------------------- #
    tasks += [
        _t("batch_social", "batch_dedup", "social",
           "Building a feed issues one avatar fetch per post in a loop, so a "
           "page with many posts from the same authors fires hundreds of "
           "redundant profile requests."),
        _t("batch_maps", "batch_dedup", "maps",
           "A trip planner geocodes each stop one-by-one inside a loop, "
           "re-geocoding the same repeated addresses and hammering the API."),
        _t("batch_ml", "batch_dedup", "ml-serving",
           "An inference wrapper calls the model once per example in a Python "
           "loop, ignoring that many inputs are identical and could be embedded "
           "in a single batched call."),
        _t("batch_email", "batch_dedup", "marketing",
           "A campaign sender looks up each recipient's unsubscribe status with "
           "a separate query per email, repeating lookups for duplicate "
           "addresses across segments."),
    ]

    # --- guard_clause across surfaces --------------------------------- #
    tasks += [
        _t("guard_form", "guard_clause", "forms",
           "A validation function nests four levels of if-checks for empty, "
           "malformed, expired, and over-limit input; the happy path is buried "
           "and unreadable.",
           Verifier("classify",
                    [((-1,), "invalid"), ((0,), "zero"), ((5,), "ok")],
                    "def classify(n):\n"
                    "    if n < 0: return 'invalid'\n"
                    "    if n == 0: return 'zero'\n"
                    "    return 'ok'")),
        _t("guard_game", "guard_clause", "gamedev",
           "An ability-cast handler wraps the whole effect in nested checks for "
           "cooldown, mana, range, and stun; the actual cast is indented five "
           "blocks deep."),
        _t("guard_fs", "guard_clause", "filesystem",
           "A file-import routine nests checks for existence, permission, size, "
           "and encoding around the read, so the core logic is hard to follow "
           "and edge cases leak."),
        _t("guard_auth", "guard_clause", "auth",
           "A request authorizer nests token-present, token-valid, scope-ok, and "
           "rate-ok conditions; the grant path is deeply indented and a missing "
           "early return causes a fall-through bug."),
    ]

    # --- accumulator across surfaces ---------------------------------- #
    tasks += [
        _t("acc_report", "accumulator", "reporting",
           "A CSV exporter builds the output by `s = s + line` for each of "
           "millions of rows, so report generation is quadratic and times out.",
           Verifier("join_rows",
                    [(([ "a", "b", "c" ],), "a\nb\nc")],
                    "def join_rows(rows):\n    return '\\n'.join(rows)")),
        _t("acc_log", "accumulator", "observability",
           "A log shipper concatenates each event onto a growing string before "
           "flushing, and the per-line copy makes high-volume nodes fall "
           "behind."),
        _t("acc_dna", "accumulator", "bioinformatics",
           "A FASTA writer appends each base to a string in a loop when emitting "
           "long chromosomes, so memory churn dominates the run."),
        _t("acc_chat", "accumulator", "chat",
           "A transcript builder grows the conversation string with `+=` per "
           "message token, and long sessions get slower the longer they run."),
    ]

    return tasks


# --------------------------------------------------------------------------- #
# Decorrelation analysis (the §10.2 first question)
# --------------------------------------------------------------------------- #
@dataclass
class PairStat:
    a: str
    b: str
    problem_sim: float
    solution_sim: float
    same_schema: bool
    same_surface: bool


@dataclass
class DecorrelationReport:
    n_tasks: int
    n_pairs: int
    pearson_r: float  # corr(problem_sim, solution_sim) across all pairs
    target_cell_pairs: int  # low problem-sim AND high solution-sim (method transfer)
    answer_copy_pairs: int  # high problem-sim (near-duplicate; the GoT win)
    separability_auc: float  # can solution_sim tell same- from different-schema pairs?
    mean_solsim_same_schema: float
    mean_solsim_diff_schema: float
    # The *non-trivial* quantity: did we actually achieve surface diversity for
    # same-method tasks?  We want this LOW (decorrelation on the surface side).
    mean_probsim_same_schema: float
    mean_probsim_diff_schema: float
    thresholds: dict
    feasible: bool
    verdict: str
    construction_note: str = ""
    pairs: list[PairStat] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["pairs"] = [p.__dict__ for p in self.pairs]
        return d


def _cos_matrix(vecs: np.ndarray) -> np.ndarray:
    return vecs @ vecs.T  # rows are L2-normalized by the embedder


def _auc(pos: list[float], neg: list[float]) -> float:
    """AUC that solution_sim separates same-schema (pos) from diff-schema (neg)."""
    if not pos or not neg:
        return float("nan")
    wins = 0.0
    for p in pos:
        for n in neg:
            wins += 1.0 if p > n else (0.5 if p == n else 0.0)
    return wins / (len(pos) * len(neg))


def decorrelation_report(
    tasks: Optional[list[Task]] = None,
    embedder: Optional[Embedder] = None,
    *,
    low_q: float = 1 / 3,
    high_q: float = 2 / 3,
    min_target_pairs: int = 8,
    max_pearson: float = 0.7,
) -> DecorrelationReport:
    """Measure whether the low-problem / high-solution cell is constructible.

    Cells are defined by *quantiles* of the observed similarity distributions, so
    the analysis is embedder-agnostic (the hashing default and a real model live
    on different cosine scales).  Feasible iff the target cell is populated AND
    surface/method don't covary too tightly to separate.
    """
    tasks = tasks if tasks is not None else build_dataset()
    embedder = embedder or default_embedder()

    pvecs = embedder.embed([t.problem_text for t in tasks])
    svecs = embedder.embed([t.solution_sketch for t in tasks])
    P = _cos_matrix(pvecs)
    S = _cos_matrix(svecs)

    stats: list[PairStat] = []
    for i, j in itertools.combinations(range(len(tasks)), 2):
        stats.append(PairStat(
            a=tasks[i].id, b=tasks[j].id,
            problem_sim=float(P[i, j]), solution_sim=float(S[i, j]),
            same_schema=tasks[i].schema_id == tasks[j].schema_id,
            same_surface=tasks[i].surface_domain == tasks[j].surface_domain,
        ))

    psim = np.array([s.problem_sim for s in stats])
    ssim = np.array([s.solution_sim for s in stats])
    r = float(np.corrcoef(psim, ssim)[0, 1]) if len(stats) > 1 else float("nan")

    p_lo = float(np.quantile(psim, low_q))
    p_hi = float(np.quantile(psim, high_q))
    s_hi = float(np.quantile(ssim, high_q))

    target = sum(1 for s in stats if s.problem_sim <= p_lo and s.solution_sim >= s_hi)
    answer_copy = sum(1 for s in stats if s.problem_sim >= p_hi)

    same = [s.solution_sim for s in stats if s.same_schema]
    diff = [s.solution_sim for s in stats if not s.same_schema]
    auc = _auc(same, diff)
    psim_same = [s.problem_sim for s in stats if s.same_schema]
    psim_diff = [s.problem_sim for s in stats if not s.same_schema]

    feasible = (target >= min_target_pairs) and (abs(r) < max_pearson) and (auc > 0.75)
    if feasible:
        verdict = (
            f"FEASIBLE: {target} pairs populate the low-problem/high-solution cell; "
            f"corr(surface,method)={r:+.2f} (<{max_pearson}); solution-sim separates "
            f"same- vs different-schema pairs at AUC={auc:.2f}. The method-transfer "
            "cell can be isolated — Phase 0 can run."
        )
    else:
        why = []
        if target < min_target_pairs:
            why.append(f"target cell underpopulated ({target}<{min_target_pairs})")
        if abs(r) >= max_pearson:
            why.append(f"surface and method covary too hard (|r|={abs(r):.2f})")
        if not (auc > 0.75):
            why.append(f"solution-sim does not cleanly separate schemas (AUC={auc:.2f})")
        verdict = ("NOT FEASIBLE: " + "; ".join(why) +
                   ". Per spec §14.4, stop and report rather than run an experiment "
                   "whose key cell cannot be isolated.")

    construction_note = (
        "Solution sketches are authored from shared per-schema templates, so "
        "within-schema solution-similarity is high by construction (AUC near 1.0 "
        "is therefore a property of how the seed set was built, not evidence). "
        "The load-bearing, non-trivial result is on the SURFACE side: same-method "
        f"tasks were made dissimilar in problem text (mean within-schema "
        f"problem-sim={np.mean(psim_same):.3f} vs cross-schema "
        f"{np.mean(psim_diff):.3f}). Before pre-registration, re-run with the "
        "pinned eval embedder and human-authored solution references to get an "
        "honest (lower, noisier) separability estimate."
    )

    return DecorrelationReport(
        n_tasks=len(tasks), n_pairs=len(stats), pearson_r=r,
        target_cell_pairs=target, answer_copy_pairs=answer_copy,
        separability_auc=auc,
        mean_solsim_same_schema=float(np.mean(same)) if same else float("nan"),
        mean_solsim_diff_schema=float(np.mean(diff)) if diff else float("nan"),
        mean_probsim_same_schema=float(np.mean(psim_same)) if psim_same else float("nan"),
        mean_probsim_diff_schema=float(np.mean(psim_diff)) if psim_diff else float("nan"),
        thresholds={"problem_low": p_lo, "problem_high": p_hi, "solution_high": s_hi,
                    "max_pearson": max_pearson, "min_target_pairs": min_target_pairs},
        feasible=feasible, verdict=verdict, construction_note=construction_note,
        pairs=stats,
    )
