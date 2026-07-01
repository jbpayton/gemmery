"""End-to-end Phase-0 orchestrator (spec §10, §14.4-14.6).

Order of operations is the scientific protocol, not a convenience:

  1. Pre-register the decision rule **as a git commit** (before any run).
  2. Answer the dataset decorrelation question (§10.2) — if the target cell can't
     be built, STOP and report. The experiment is not run.
  3. Only if feasible: run exploratory, then (if green) the pre-registered
     confirmation at higher n. Report the verdict + the compute report.

Everything is written to a result artifact so the compute report and the
go/no-go are impossible to skip (spec §10.4).

Run:  python -m gemmery.eval.run_phase0 [--gain G] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset import build_dataset, decorrelation_report
from .harness import Phase0Config
from .preregister import commit_prereg, default_prereg
from .replication import run_with_replication
from .tasks_v2 import build_tasks, validate_discrimination


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gemmery Phase-0 kill-switch")
    ap.add_argument("--gain", type=float, default=0.5,
                    help="SimulatedSolver transfer_gain (0 => memory inert; "
                         "use to confirm the kill-switch can refuse).")
    ap.add_argument("--budget-calls", type=int, default=8)
    ap.add_argument("--n-exploratory", type=int, default=40)
    ap.add_argument("--n-confirmatory", type=int, default=98)
    ap.add_argument("--dataset", choices=["v1", "v2"], default="v2",
                    help="v2 = open-ended objective-scored tasks (default); "
                         "v1 = the over-constrained seed set.")
    ap.add_argument("--out", type=str, default="phase0_artifacts")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    use_v2 = args.dataset == "v2"
    tasks = build_tasks() if use_v2 else build_dataset()

    # 1. Pre-register (commit BEFORE running) ----------------------------- #
    prereg = default_prereg(n_exploratory=args.n_exploratory,
                            n_confirmatory=args.n_confirmatory)
    sha = commit_prereg(prereg, out / "prereg_repo")
    print(f"[1] pre-registration committed: {sha[:12]} "
          f"({out / 'prereg_repo'})")

    # 1b. Verifier discrimination gate (v2 only) — a verifier that can't tell a
    # strong approach from a weak one can't measure whether memory helped.
    if use_v2:
        disc = validate_discrimination(tasks)
        bad = [d.task_id for d in disc if not d.discriminates]
        print(f"[1b] discrimination: {len(disc) - len(bad)}/{len(disc)} verifiers "
              f"separate strong vs naive" + (f"; BAD={bad}" if bad else ""))
        if bad:
            print("STOP: non-discriminating verifiers — fix before running.")
            return 1

    # 2. Decorrelation feasibility gate (§10.2) --------------------------- #
    rep = decorrelation_report(tasks)
    (out / "decorrelation.json").write_text(json.dumps(rep.to_dict(), indent=2))
    print(f"[2] decorrelation: feasible={rep.feasible} | "
          f"target-cell pairs={rep.target_cell_pairs} | "
          f"r(surface,method)={rep.pearson_r:+.2f}")
    print("    " + rep.verdict)
    if not rep.feasible:
        print("\nSTOP (spec §14.4): the method-transfer cell cannot be isolated. "
              "Report this as the finding; do not run the experiment.")
        (out / "RESULT.json").write_text(json.dumps(
            {"stopped_at": "decorrelation", "feasible": False,
             "verdict": rep.verdict}, indent=2))
        return 0

    # 3. Exploratory -> pre-registered confirmation ----------------------- #
    cfg = Phase0Config(budget_calls=args.budget_calls, transfer_gain=args.gain)
    outcome = run_with_replication(
        cfg, n_exploratory=args.n_exploratory,
        n_confirmatory=args.n_confirmatory, n_tasks=len(tasks), tasks=tasks)

    artifact = {
        "prereg_sha": sha,
        "decorrelation": rep.to_dict(),
        "replication": outcome.to_dict(),
    }
    (out / "RESULT.json").write_text(json.dumps(artifact, indent=2))

    print(f"[3] {outcome.summary}")
    exp = outcome.exploratory
    print(f"    compute report: {exp.compute_note}")
    print(f"\nArtifact written: {out / 'RESULT.json'}")
    print(f"GREEN-LIGHT to build credit/operators: {outcome.believed}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
