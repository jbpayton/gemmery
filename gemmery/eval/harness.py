"""Phase-0 harness: the three arms + the green-light decision rule (spec §10).

Arms (spec §10.1):
  1. ``browse + memory``      — full browse loop over a populated store.
  2. ``one_shot + memory``    — single static top-k lookup (the GitOfThoughts modality).
  3. ``browse + empty memory``— same loop, same budget, EMPTY store. The kill-switch.

The only comparison that proves memory is load-bearing is **arm 1 vs arm 3 at
matched compute** (spec §10.4): both run the identical browse loop at the same
budget; only the store content differs.  If arm 1 can't beat arm 3, we have
merely rediscovered that thinking longer helps.  Arm 3 is not optional, and the
compute report is part of the result artifact.

Evaluation is leave-one-out over the dataset: each task is a query whose own gem
is excluded, so any lift must come from *transfer* off a different-surface,
same-method gem — never from copying itself.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from ..browse import BudgetMeter, MockPolicy, Permeability, browse, one_shot
from ..browse.policy import Mark
from ..index import GemIndex
from ..model import (
    Action,
    Cost,
    DecisionBody,
    Gem,
    IndexKeys,
    Kind,
    Provenance,
    Reversibility,
    TestSpec,
)
from ..store import GitStore
from .dataset import SCHEMAS, Task, build_dataset
from .solver import SimulatedSolver, Solver

# Method-level precondition tokens per schema, shared across surfaces — this is
# the solution-shape handle that makes cross-surface transfer findable (spec §5).
_METHOD_TOKENS = {
    "memoize": ["cache", "memoize", "recompute", "pure", "repeated", "same", "result"],
    "retry_backoff": ["retry", "backoff", "transient", "idempotent", "flaky", "timeout"],
    "index_lookup": ["index", "lookup", "scan", "linear", "dict", "search", "id"],
    "batch_dedup": ["batch", "dedup", "loop", "per", "redundant", "unique", "calls"],
    "guard_clause": ["guard", "early", "return", "nested", "edge", "validate", "flatten"],
    "accumulator": ["accumulate", "concatenation", "append", "join", "quadratic", "loop"],
}


@dataclass
class Phase0Config:
    runs: int = 5
    budget_calls: int = 8          # the matched compute ceiling (all arms)
    transfer_gain: float = 0.5     # simulated solver knob (0 => memory inert)
    base_rate: float = 0.30
    top_k: int = 8
    max_iters: int = 4
    permeability: Permeability = Permeability.sealed
    green_margin: float = 0.05     # arm1 must beat arm3 by >= this (draft, §10.3)
    seed: str = "phase0"


@dataclass
class ArmResult:
    name: str
    n_trials: int
    success_rate: float
    recognition_rate: float
    mean_calls: float
    mean_tokens: float
    per_task_rate: dict[str, float] = field(default_factory=dict)


@dataclass
class Phase0Result:
    arms: dict[str, ArmResult]
    effect: float                  # arm1_rate - arm3_rate (the memory effect)
    effect_ci95: tuple[float, float]
    compute_matched: bool
    compute_note: str
    green_light: bool
    decision: str
    config: dict

    def to_dict(self) -> dict:
        d = {
            "arms": {k: v.__dict__ for k, v in self.arms.items()},
            "effect": self.effect,
            "effect_ci95": list(self.effect_ci95),
            "compute_matched": self.compute_matched,
            "compute_note": self.compute_note,
            "green_light": self.green_light,
            "decision": self.decision,
            "config": self.config,
        }
        return d


# --------------------------------------------------------------------------- #
# Memory population
# --------------------------------------------------------------------------- #
def task_to_gem(task: Task) -> Gem:
    """Represent a past-solved task as a decision gem.

    ``action_type`` = schema id (the method handle, used for transfer matching);
    ``domain`` = surface; ``precondition_shape`` = shared method tokens (the
    solution-shape index, spec §5); reasoning = the method sketch.
    """
    tid = task.verifier.test_id if task.verifier else f"unit::{task.id}"
    return Gem(
        kind=Kind.decision,
        provenance=Provenance(actor="eval", session_id="memory"),
        body=DecisionBody(
            action=Action(task.schema_id, {"task": task.id}),
            reasoning=task.solution_sketch,
            tests=[TestSpec(tid, "run verifier", "all cases pass")],
            pre={"schema": task.schema_id, "surface": task.surface_domain},
        ),
        cost=Cost(tokens=0),
        reversibility_class=Reversibility.pure,
        index_keys=IndexKeys(
            precondition_shape=_METHOD_TOKENS.get(task.schema_id, [task.schema_id]),
            action_type=task.schema_id,
            domain=[task.surface_domain],
            test_ids=[tid],
        ),
    )


def populate_memory(store: GitStore, tasks: list[Task]) -> dict[str, str]:
    """Capture one gem per task and mark each solved (success note + ok tag)."""
    sha_by_task: dict[str, str] = {}
    for t in tasks:
        gem = task_to_gem(t)
        sha = store.capture(gem).sha
        tid = gem.tests()[0].id
        store.attach_success(sha, tid, 1.0, source="seed")
        store.tag_outcome(sha, tid, ok=True)
        sha_by_task[t.id] = sha
    return sha_by_task


# --------------------------------------------------------------------------- #
# Running the arms
# --------------------------------------------------------------------------- #
def _bootstrap_ci(paired_diffs: np.ndarray, iters: int = 2000,
                  seed: int = 0xC0FFEE) -> tuple[float, float]:
    if len(paired_diffs) == 0:
        return (float("nan"), float("nan"))
    n = len(paired_diffs)
    # Deterministic (fixed-seed) paired bootstrap of the mean difference.
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(iters, n))
    means = paired_diffs[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return (float(lo), float(hi))


def run_phase0(config: Optional[Phase0Config] = None,
               tasks: Optional[list[Task]] = None,
               solver: Optional[Solver] = None,
               policy_factory: Callable[[], object] = MockPolicy,
               workdir: Optional[str] = None,
               embedder=None) -> Phase0Result:
    cfg = config or Phase0Config()
    tasks = tasks if tasks is not None else build_dataset()

    # The embedder is swappable: the dependency-free hashing default for offline
    # tests; the pinned eval embedder (sentence-transformers) for a real run.
    def _index() -> GemIndex:
        return GemIndex(embedder=embedder) if embedder is not None else GemIndex()

    tmp = workdir or tempfile.mkdtemp(prefix="gemmery-phase0-")
    mem_store = GitStore(Path(tmp) / "memory")
    sha_by_task = populate_memory(mem_store, tasks)
    mem_index = _index()
    mem_index.rebuild(mem_store)

    # arm 3's empty store + index (true control: same loop, nothing to find)
    empty_store = GitStore(Path(tmp) / "empty")
    empty_index = _index()
    empty_index.rebuild(empty_store)

    # Solvers. arm1/arm3 solve with best_of=1 (budget spent on browsing);
    # arm2 (one-shot) spends its freed browse budget on best_of solve attempts.
    base_solver = solver or SimulatedSolver(transfer_gain=cfg.transfer_gain,
                                            base_rate=cfg.base_rate)
    oneshot_solver = (solver or SimulatedSolver(
        transfer_gain=cfg.transfer_gain, base_rate=cfg.base_rate,
        best_of=max(1, cfg.budget_calls)))

    acc = {name: {"succ": [], "recog": [], "calls": [], "tokens": [],
                  "per_task": {}} for name in
           ("browse+memory", "one_shot+memory", "browse+empty")}

    for r in range(cfg.runs):
        for t in tasks:
            trial_key = f"{cfg.seed}:r{r}"
            exclude = {sha_by_task[t.id]}
            goal = t.problem_text

            # arm 1: browse + memory
            m1 = BudgetMeter(max_calls=cfg.budget_calls)
            res1 = browse(goal, store=mem_store, index=mem_index,
                          policy=policy_factory(), budget=m1,
                          permeability=cfg.permeability, exclude=exclude,
                          top_k=cfg.top_k, max_iters=cfg.max_iters)
            marks1 = [Mark(sha=s, reason="", relevance=1.0) for s in res1.mark_shas]
            out1 = base_solver.solve(t, marks1, mem_store, m1, trial_key=trial_key)
            _record(acc["browse+memory"], t, out1, m1)

            # arm 2: one-shot + memory  (matched compute via solve-side best_of)
            m2 = BudgetMeter(max_calls=cfg.budget_calls)
            res2 = one_shot(goal, store=mem_store, index=mem_index, budget=m2,
                            permeability=cfg.permeability, exclude=exclude,
                            top_k=cfg.top_k)
            marks2 = [Mark(sha=s, reason="", relevance=1.0) for s in res2.mark_shas]
            out2 = oneshot_solver.solve(t, marks2, mem_store, m2, trial_key=trial_key)
            _record(acc["one_shot+memory"], t, out2, m2)

            # arm 3: browse + EMPTY memory (the kill-switch control)
            m3 = BudgetMeter(max_calls=cfg.budget_calls)
            res3 = browse(goal, store=empty_store, index=empty_index,
                          policy=policy_factory(), budget=m3,
                          permeability=cfg.permeability,
                          top_k=cfg.top_k, max_iters=cfg.max_iters)
            out3 = base_solver.solve(t, [], empty_store, m3, trial_key=trial_key)
            _record(acc["browse+empty"], t, out3, m3)

    arms = {name: _summarize(name, data) for name, data in acc.items()}

    a1, a3 = arms["browse+memory"], arms["browse+empty"]
    # paired per-task differences (averaged within task across runs)
    keys = sorted(set(a1.per_task_rate) & set(a3.per_task_rate))
    diffs = np.array([a1.per_task_rate[k] - a3.per_task_rate[k] for k in keys])
    effect = float(np.mean(diffs)) if len(diffs) else 0.0
    ci = _bootstrap_ci(diffs)

    # matched-compute check: arm1 and arm3 must spend ~equal model calls.
    matched = abs(a1.mean_calls - a3.mean_calls) <= 0.5
    a2 = arms["one_shot+memory"]
    compute_note = (
        f"arm1 mean calls={a1.mean_calls:.2f}, arm3 mean calls={a3.mean_calls:.2f} "
        f"(matched={matched}); arm2 mean calls={a2.mean_calls:.2f}, "
        f"rate={a2.success_rate:.3f}. The go/no-go uses ONLY arm1 vs arm3: arm2 "
        "spends its freed browse budget on extra solve attempts, so a high arm2 "
        "rate can be a relabeled-compute artifact (watch it stay high even at "
        "transfer_gain=0) and must not be read as a memory win (spec §10.4)."
    )

    green = bool(matched and effect >= cfg.green_margin and ci[0] > 0.0)
    decision = _decision_text(effect, ci, cfg, matched, green)

    return Phase0Result(
        arms=arms, effect=effect, effect_ci95=ci,
        compute_matched=matched, compute_note=compute_note,
        green_light=green, decision=decision,
        config={**cfg.__dict__, "permeability": cfg.permeability.value,
                "n_tasks": len(tasks)},
    )


def _record(bucket, task, outcome, meter) -> None:
    succ = max(outcome.scores.values()) if outcome.scores else 0.0
    bucket["succ"].append(succ)
    bucket["recog"].append(1.0 if outcome.method_recognized else 0.0)
    bucket["calls"].append(meter.calls)
    bucket["tokens"].append(meter.tokens)
    bucket["per_task"].setdefault(task.id, []).append(succ)


def _summarize(name, data) -> ArmResult:
    per_task = {k: float(np.mean(v)) for k, v in data["per_task"].items()}
    return ArmResult(
        name=name,
        n_trials=len(data["succ"]),
        success_rate=float(np.mean(data["succ"])) if data["succ"] else 0.0,
        recognition_rate=float(np.mean(data["recog"])) if data["recog"] else 0.0,
        mean_calls=float(np.mean(data["calls"])) if data["calls"] else 0.0,
        mean_tokens=float(np.mean(data["tokens"])) if data["tokens"] else 0.0,
        per_task_rate=per_task,
    )


def _decision_text(effect, ci, cfg, matched, green) -> str:
    if not matched:
        return ("INVALID: arm1 and arm3 compute not matched — cannot attribute any "
                "difference to memory vs compute. Re-run with equalized budgets.")
    if green:
        return (
            f"GREEN (exploratory): browse+memory beats browse+empty by "
            f"{effect:+.3f} (95% CI {ci[0]:+.3f}..{ci[1]:+.3f}) at matched compute, "
            f"margin>={cfg.green_margin}. Per spec §10.3 this must REPLICATE at "
            "higher n before Phase 1+ is built."
        )
    return (
        f"NO GREEN LIGHT: memory effect {effect:+.3f} (95% CI {ci[0]:+.3f}.."
        f"{ci[1]:+.3f}) does not clear margin {cfg.green_margin} with CI>0 at "
        "matched compute. Under spec §10.3, ship Gemmery as an audit/coordination "
        "system only; do not build credit/operators on this evidence."
    )
