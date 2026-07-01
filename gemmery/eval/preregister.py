"""Pre-registration as git commits (spec §10, §10.3).

Pre-registrations are themselves git commits: decision rules committed *before*
the first run, so the commit history is the audit trail.  This makes p-hacking
visible — you cannot quietly move the goalposts after seeing the data without it
showing up as a later commit.

A pre-registration records (spec §10.3): hypotheses, the primary metric, the
test-cell definition, the compute-matching protocol, the ``n`` for adequate
power, and the decision (green-light) rule.  It is stored in its own tiny git
repo (or any path) so it is independent of the gem store.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PreRegistration:
    title: str
    hypotheses: list[str]
    primary_metric: str
    test_cell: str
    compute_matching: str
    n_exploratory: int
    n_confirmatory: int
    green_light_rule: str
    decision_thresholds: dict
    created_iso: str = ""
    notes: str = ""

    def to_markdown(self) -> str:
        L = [f"# Pre-registration: {self.title}", ""]
        L.append(f"_committed: {self.created_iso}_\n")
        L.append("## Hypotheses")
        L += [f"- {h}" for h in self.hypotheses]
        L.append("\n## Primary metric")
        L.append(self.primary_metric)
        L.append("\n## Test cell (where method transfer is visible)")
        L.append(self.test_cell)
        L.append("\n## Compute-matching protocol")
        L.append(self.compute_matching)
        L.append("\n## Power")
        L.append(f"- exploratory n = {self.n_exploratory}")
        L.append(f"- confirmatory n = {self.n_confirmatory}")
        L.append("\n## Green-light rule")
        L.append(self.green_light_rule)
        L.append("\n## Decision thresholds")
        L.append("```json")
        L.append(json.dumps(self.decision_thresholds, indent=2))
        L.append("```")
        if self.notes:
            L.append("\n## Notes")
            L.append(self.notes)
        return "\n".join(L) + "\n"


def default_prereg(*, n_exploratory: int = 40, n_confirmatory: int = 98,
                   green_margin: float = 0.05) -> PreRegistration:
    """The draft pre-registration for Phase 0 (finalize before the first run)."""
    return PreRegistration(
        title="Gemmery Phase 0 — is cross-problem agent memory load-bearing?",
        hypotheses=[
            "H1: browse+memory beats browse+empty-memory on task success rate at "
            "matched compute, in the low-problem/high-solution cell.",
            "H0 (null we must be able to accept): any apparent lift is explained "
            "by extra test-time compute, not by memory content.",
        ],
        primary_metric="Task success rate under bound automatic verifiers "
                       "(signed, per-test; primary = fraction with score == +1).",
        test_cell="Pairs decorrelating problem-surface from solution-schema "
                  "similarity; measure in low problem-sim / high solution-sim "
                  "(method transfer). Domain: SWE/config/design with cheap "
                  "automatic verifiers (compile/test/typecheck).",
        compute_matching="All arms share one model-call/token ceiling. The "
                         "mandatory comparison is arm1 (browse+memory) vs arm3 "
                         "(browse+empty) running the identical loop at the same "
                         "budget; only store content differs. Per-arm compute is "
                         "logged and the effect reported only after equalizing it. "
                         "arm3 is not optional.",
        n_exploratory=n_exploratory,
        n_confirmatory=n_confirmatory,
        green_light_rule=(
            "Build Phase 1+ (credit, then operators) only if browse+memory beats "
            "browse+empty-memory by >= margin, with the 95% CI lower bound > 0, at "
            "matched compute, in the target cell, AND the effect replicates at "
            "confirmatory n. Anything less: ship Gemmery as an audit/coordination "
            "system only and shelve the smarter-agent claim (spec §10.3)."
        ),
        decision_thresholds={
            "green_margin": green_margin,
            "ci_lower_must_exceed": 0.0,
            "require_compute_matched": True,
            "require_replication": True,
            "do_not_trust_small_n": "GitOfThoughts +15pp died from n=40 to n=98",
        },
        created_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


def commit_prereg(prereg: PreRegistration, repo_path: str | Path,
                  *, actor: str = "gemmery-eval",
                  email: str = "eval@gemmery.local") -> str:
    """Write the pre-registration and commit it. Returns the commit sha.

    Committed *before* the first run — the commit timestamp is the proof of
    precedence (spec §10.3).
    """
    repo = Path(repo_path)
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        _run(repo, ["init", "-q"])
        _run(repo, ["config", "user.name", actor])
        _run(repo, ["config", "user.email", email])

    stamp = prereg.created_iso.replace(":", "").replace("-", "")
    fname = f"prereg-{stamp}.md"
    (repo / fname).write_text(prereg.to_markdown())
    (repo / fname.replace(".md", ".json")).write_text(
        json.dumps(asdict(prereg), indent=2)
    )
    _run(repo, ["add", "-A"])
    _run(repo, ["commit", "-q", "-m",
                f"pre-register: {prereg.title}\n\n"
                f"Committed before first run; n_exp={prereg.n_exploratory} "
                f"n_conf={prereg.n_confirmatory}. The audit trail is the point."])
    return _run(repo, ["rev-parse", "HEAD"]).strip()


def _run(repo: Path, args: list[str]) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout
