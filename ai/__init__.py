"""KAYAN AI layer: cloud LLM providers, MITRE RAG and parallel agents.

This package is deliberately separate from the legacy sequential agent runtime in
``pentagi/``. New code here must still route every sensitive action through
TrustGate; an LLM decision is never an authorization decision.
"""

__all__ = ["config", "providers", "mitre", "orchestrator", "trustgate"]
