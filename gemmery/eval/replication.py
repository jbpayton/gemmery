"""Replication runner (spec §10.3): exploratory, then pre-registered confirm.

"Any positive at exploratory n must survive a pre-registered confirmation at
higher n before it is believed."  The GitOfThoughts +15pp died from n=40 to
n=98 — so a single exploratory green is *not* a result.  This runner reports
nulls and retractions as first-class outcomes (the substrate makes that cheap).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .harness import Phase0Config, Phase0Result, run_phase0


@dataclass
class ReplicationOutcome:
    exploratory: Phase0Result
    confirmatory: Optional[Phase0Result]
    believed: bool
    summary: str

    def to_dict(self) -> dict:
        return {
            "exploratory": self.exploratory.to_dict(),
            "confirmatory": self.confirmatory.to_dict() if self.confirmatory else None,
            "believed": self.believed,
            "summary": self.summary,
        }


def _runs_for_n(n_trials: int, n_tasks: int) -> int:
    # Each run is one leave-one-out sweep (n_tasks trials). Scale runs to hit ~n.
    return max(1, round(n_trials / max(1, n_tasks)))


def run_with_replication(
    base_config: Phase0Config,
    *,
    n_exploratory: int = 40,
    n_confirmatory: int = 98,
    n_tasks: int = 24,
    **run_kwargs,
) -> ReplicationOutcome:
    """Run exploratory; only if it greens, run the confirmation at higher n.

    A result is *believed* only if BOTH stages green at matched compute.  An
    exploratory green that fails to confirm is reported as a retraction — the
    correct, cheap outcome the spec wants surfaced (spec §10.3).
    """
    exp_cfg = Phase0Config(**{**base_config.__dict__,
                              "runs": _runs_for_n(n_exploratory, n_tasks)})
    exploratory = run_phase0(exp_cfg, **run_kwargs)

    if not exploratory.green_light:
        return ReplicationOutcome(
            exploratory=exploratory, confirmatory=None, believed=False,
            summary=(f"Exploratory NOT green (effect {exploratory.effect:+.3f}). "
                     "No confirmation run. Do not build Phase 1+; ship as "
                     "audit/coordination system (spec §10.3)."),
        )

    conf_cfg = Phase0Config(**{**base_config.__dict__,
                               "runs": _runs_for_n(n_confirmatory, n_tasks)})
    confirmatory = run_phase0(conf_cfg, **run_kwargs)

    believed = bool(confirmatory.green_light)
    if believed:
        summary = (
            f"REPLICATED. exploratory effect {exploratory.effect:+.3f}, "
            f"confirmatory {confirmatory.effect:+.3f} (95% CI "
            f"{confirmatory.effect_ci95[0]:+.3f}..{confirmatory.effect_ci95[1]:+.3f}) "
            f"at matched compute and n~{n_confirmatory}. Green-light to build "
            "credit/, then operators/ (spec §10.3, §14.6)."
        )
    else:
        summary = (
            f"RETRACTION. Exploratory greened (effect {exploratory.effect:+.3f}) "
            f"but confirmation at n~{n_confirmatory} did NOT "
            f"(effect {confirmatory.effect:+.3f}, CI "
            f"{confirmatory.effect_ci95[0]:+.3f}..{confirmatory.effect_ci95[1]:+.3f}). "
            "Per the GitOfThoughts precedent, this is the expected failure mode of "
            "small-n positives. Do not build Phase 1+. Report the null."
        )
    return ReplicationOutcome(exploratory=exploratory, confirmatory=confirmatory,
                              believed=believed, summary=summary)
