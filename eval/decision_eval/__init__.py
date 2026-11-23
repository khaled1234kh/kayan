"""Offline-first decision-evaluation framework for KAYAN's five agents.

Design rules (all enforced in code where possible):
  * The frozen 80-case role-contract scorer is the historical baseline and is
    never edited. Improved rubrics are versioned and reported alongside it.
  * Deterministic scoring is primary. DeepEval / LLM-judge output is
    supplementary and cannot become ground truth.
  * No network call, paid judge call or cloud inference happens by default.
  * Human labels remain ``provisional`` until real independent reviewers and
    an adjudicator attest and sign them.
"""
from __future__ import annotations

SCHEMA_VERSION = "kayan.decision-eval/1"
RUBRIC_VERSION = "role-contract-frozen+diagnostics-v1"
PROTOCOL_VERSION = "kayan-inference-protocol/1"
DATASET_REVISION = "decision-cases-v0.1-provisional"
AGENTS = ("Planner", "Recon", "Web-App", "Network", "Reporting")
CANONICAL_CLASSES = ("supported", "contradicted", "abstain")

__all__ = [
    "SCHEMA_VERSION", "RUBRIC_VERSION", "PROTOCOL_VERSION",
    "DATASET_REVISION", "AGENTS", "CANONICAL_CLASSES",
]
