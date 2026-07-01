"""The delivered Claude skill (spec §11).

Gemmery is consumed by agents as a skill: capture and retrieval are *intentional*
tool actions, never a background hook (Invariant 5).  This package holds
``SKILL.md`` (the trigger surface + imperative body), ``scripts/`` (thin wrappers
over ``gemmery.cli``), ``references/`` (schema + browse patterns + the gated
credit/operators detail), and ``evals/`` (skill-triggering tests).
"""
