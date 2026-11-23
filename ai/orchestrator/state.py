"""State shared by the parallel LangGraph agents.

Lists use ``operator.add`` reducers so concurrent agents cannot overwrite each
other's results.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AgentResultDict(TypedDict):
    agent: str
    summary: str
    findings: list[dict[str, Any]]
    recommendations: list[str]
    citations: list[str]
    hallucinated_technique_ids: list[str]
    provider: str
    model: str
    latency_s: float
    error: str


class TrustGateDecisionDict(TypedDict):
    agent: str
    action: str
    allowed: bool
    reason: str
    response: dict[str, Any]


class AssessmentState(TypedDict, total=False):
    founder_request: str
    evidence: str
    engagement_id: str
    tasks: list[str]
    agent_results: Annotated[list[AgentResultDict], operator.add]
    trustgate_decisions: Annotated[list[TrustGateDecisionDict], operator.add]
    errors: Annotated[list[str], operator.add]
    consolidated: dict[str, Any]
    provider: str
    top_k: int
