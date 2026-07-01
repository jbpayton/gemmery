from gemmery.eval import (
    Phase0Config,
    SimulatedSolver,
    build_dataset,
    commit_prereg,
    decorrelation_report,
    default_prereg,
    run_phase0,
    run_verifier,
    task_to_gem,
)
from gemmery.eval.replication import run_with_replication


def test_decorrelation_target_cell_is_constructible():
    rep = decorrelation_report(build_dataset())
    # The §10.2 first question: can we populate low-problem/high-solution?
    assert rep.feasible
    assert rep.target_cell_pairs >= rep.thresholds["min_target_pairs"]
    assert abs(rep.pearson_r) < rep.thresholds["max_pearson"]
    # surface diversity actually achieved for same-method tasks
    assert rep.mean_probsim_same_schema < 0.5


def test_kill_switch_refuses_when_memory_inert():
    """transfer_gain=0 => memory adds nothing => NO green light (the kill-switch)."""
    res = run_phase0(Phase0Config(runs=3, transfer_gain=0.0))
    assert res.compute_matched
    assert abs(res.effect) < 1e-9
    assert res.green_light is False
    # arm1 and arm3 must be matched in compute (the mandatory comparison)
    assert abs(res.arms["browse+memory"].mean_calls
               - res.arms["browse+empty"].mean_calls) <= 0.5


def test_harness_can_green_light_when_memory_helps():
    res = run_phase0(Phase0Config(runs=6, transfer_gain=0.7, base_rate=0.25))
    assert res.compute_matched
    assert res.effect > 0
    assert res.green_light is True
    assert res.effect_ci95[0] > 0


def test_arm3_is_a_true_control_no_recognition():
    res = run_phase0(Phase0Config(runs=2, transfer_gain=0.7))
    # empty-memory arm can never recognize a transfer gem
    assert res.arms["browse+empty"].recognition_rate == 0.0


def test_replication_gate_requires_both_stages():
    inert = run_with_replication(Phase0Config(transfer_gain=0.0),
                                 n_exploratory=24, n_confirmatory=48, n_tasks=24)
    assert inert.believed is False
    assert inert.confirmatory is None  # never ran a confirmation on a non-green

    # Adequate n so the exploratory stage is actually powered to green (a small
    # n that fails to green is the GitOfThoughts lesson, tested above as 'inert').
    helped = run_with_replication(Phase0Config(transfer_gain=0.8, base_rate=0.2),
                                  n_exploratory=120, n_confirmatory=216, n_tasks=24)
    assert helped.believed is True
    assert helped.confirmatory is not None


def test_prereg_is_committed_before_running(tmp_path):
    pr = default_prereg()
    sha = commit_prereg(pr, tmp_path / "prereg")
    assert len(sha) == 40  # a real commit sha
    assert any((tmp_path / "prereg").glob("prereg-*.md"))


def test_verifier_runs_canonical_solutions():
    # every task that ships a verifier should pass its own canonical solution
    for t in build_dataset():
        if t.verifier:
            assert run_verifier(t.verifier.canonical_solution, t.verifier) == 1.0


def test_task_to_gem_maps_schema_to_action_type():
    t = next(t for t in build_dataset() if t.schema_id == "memoize")
    gem = task_to_gem(t)
    assert gem.index_keys.action_type == "memoize"
    assert t.surface_domain in gem.index_keys.domain
