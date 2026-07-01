"""``eval/`` — Phase 0, the kill-switch (spec §10). BUILD/RUN THIS FIRST.

A pre-registered, compute-matched ablation that can say *no* and kill the project
cheaply.  The expensive machinery (``credit``, ``operators``) is gated behind a
*replicated* win over the empty-memory control at matched compute.
"""

from .dataset import (
    DecorrelationReport,
    SCHEMAS,
    Task,
    Verifier,
    build_dataset,
    decorrelation_report,
)
from .harness import (
    ArmResult,
    Phase0Config,
    Phase0Result,
    populate_memory,
    run_phase0,
    task_to_gem,
)
from .preregister import PreRegistration, commit_prereg, default_prereg
from .recall import RecallReport, transfer_recall_report
from .replication import ReplicationOutcome, run_with_replication
from .solver import AnthropicSolver, SimulatedSolver, Solver, grade, run_verifier
from .tasks_v2 import (
    APPROACHES,
    ScoredVerifier,
    build_tasks,
    validate_discrimination,
)

__all__ = [
    "build_dataset",
    "decorrelation_report",
    "DecorrelationReport",
    "Task",
    "Verifier",
    "SCHEMAS",
    "Phase0Config",
    "Phase0Result",
    "ArmResult",
    "run_phase0",
    "populate_memory",
    "task_to_gem",
    "PreRegistration",
    "default_prereg",
    "commit_prereg",
    "run_with_replication",
    "ReplicationOutcome",
    "Solver",
    "SimulatedSolver",
    "AnthropicSolver",
    "run_verifier",
    "transfer_recall_report",
    "RecallReport",
    "build_tasks",
    "validate_discrimination",
    "ScoredVerifier",
    "APPROACHES",
    "grade",
]
