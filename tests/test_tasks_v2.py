from gemmery.eval import build_tasks, decorrelation_report, validate_discrimination


def test_all_verifiers_discriminate():
    """Every scored verifier must separate a strong approach from a weak one —
    otherwise it can't measure whether a method helped (the per-task kill-switch)."""
    results = validate_discrimination()
    assert results, "no tasks built"
    bad = [r for r in results if not r.discriminates]
    assert not bad, f"non-discriminating verifiers: {[(r.task_id, r.reference_score, r.naive_score) for r in bad]}"


def test_four_families_present():
    fams = {t.family for t in build_tasks()}
    assert fams == {"heuristic", "optimization", "property", "debug_feature"}


def test_open_ended_not_overconstrained():
    """Reference clears the bar; the plausible naive does NOT — i.e. there is a
    real design space, not one trivially-correct answer."""
    for r in validate_discrimination():
        assert r.reference_score >= r.threshold
        assert r.naive_score < r.threshold


def test_transfer_cell_is_constructible_v2():
    rep = decorrelation_report(build_tasks())
    assert rep.feasible
    assert abs(rep.pearson_r) < rep.thresholds["max_pearson"]
    # surface narratives were diversified: same-approach problem-sim is not high
    assert rep.mean_probsim_same_schema < 0.55


def test_prompt_separates_narrative_from_contract():
    for t in build_tasks():
        assert t.contract  # every task has an API contract
        # the function/class name lives in the contract, not the surface narrative
        assert t.verifier.entry_point in t.contract
        assert t.verifier.entry_point not in t.problem_text
        assert t.contract in t.prompt() and t.problem_text in t.prompt()


def test_reference_solutions_are_first_party_runnable():
    # sanity: a strong solution actually scores well through the live harness
    for t in build_tasks():
        assert t.verifier.score(t.verifier.reference_solution) >= t.verifier.threshold
