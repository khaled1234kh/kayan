"""LangGraph orchestrator: prepare → 4 parallel agents → aggregate.

Concurrency is intentional at the agent level. Actual model requests are still
capped by the provider semaphore (Student Plan: 2 simultaneous calls), so fanning
out four agents does not exceed the account limit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from ..config import AIConfig, require_local_http
from ..mitre.rag import MitreRAG
from ..providers.registry import ProviderRegistry
from ..trustgate.client import AITrustGate
from .agents import AGENT_ROLES, _run_agent
from .schemas import ConsolidatedAssessment
from .state import AssessmentState

log = logging.getLogger(__name__)


@dataclass
class _Resources:
    config: AIConfig
    registry: ProviderRegistry
    rag: MitreRAG
    gate: AITrustGate


def _prepare(state: AssessmentState, resources: _Resources) -> dict[str, Any]:
    tasks = [
        f"{name}: {AGENT_ROLES[name]}"
        for name in resources.config.agent_names
        if name in AGENT_ROLES
    ]
    return {"tasks": tasks}


async def _agent_node(name: str, resources: _Resources, state: AssessmentState) -> dict[str, Any]:
    result, decision = await _run_agent(
        name=name,
        state=dict(state),
        registry=resources.registry,
        rag=resources.rag,
        gate=resources.gate,
        top_k=resources.config.mitre.top_k,
    )
    return {"agent_results": [result], "trustgate_decisions": [decision]}


async def _aggregate(resources: _Resources, state: AssessmentState) -> dict[str, Any]:
    results = state.get("agent_results") or []
    decisions = state.get("trustgate_decisions") or []

    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    citations: list[str] = []
    recommendations: list[str] = []
    limitations: list[str] = []

    for result in results:
        if result.get("error"):
            limitations.append(f"{result['agent']}: {result['error']}")
        citations.extend(result.get("citations") or [])
        recommendations.extend(result.get("recommendations") or [])
        for finding in result.get("findings") or []:
            key = (finding.get("technique_id", ""), finding.get("claim", "")[:120])
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding)
        limitations.extend(
            f"{result['agent']}: unverified technique ID removed: {tid}"
            for tid in result.get("hallucinated_technique_ids") or []
        )

    for decision in decisions:
        if not decision.get("allowed"):
            limitations.append(
                f"TrustGate denied {decision['action']} for {decision['agent']}: {decision['reason']}"
            )

    summary_parts = [
        f"{r['agent']}: {r['summary']}" for r in results if r.get("summary")
    ]
    consolidated = ConsolidatedAssessment(
        executive_summary="\n".join(summary_parts)[:6000],
        findings=findings[:60],
        recommendations=list(dict.fromkeys(recommendations))[:30],
        limitations=list(dict.fromkeys(limitations))[:30],
        evidence_citations=list(dict.fromkeys(citations))[:60],
    )

    try:
        report_decision = await resources.gate.require(
            engagement_id=state["engagement_id"],
            agent_id="ai-aggregator",
            agent_role="ai-aggregator",
            action="write_report",
            target="127.0.0.1",
            technique="reporting",
            tool_args={"engagement_id": state["engagement_id"]},
        )
        if not report_decision.allowed:
            raise PermissionError("Report denied")
    except Exception:
        return {"trustgate_decisions": [{
            "agent": "ai-aggregator", "action": "write_report", "allowed": False,
            "decision": "DENY", "reason": "Report authorization unavailable or denied",
        }]}

    return {
        "consolidated": consolidated.model_dump(),
        "trustgate_decisions": [report_decision.as_dict()],
    }


def _build_assessment_graph(resources: _Resources):
    builder = StateGraph(AssessmentState)
    builder.add_node("prepare", lambda state: _prepare(state, resources))

    agents = [n for n in resources.config.agent_names if n in AGENT_ROLES]
    if not agents:
        raise ValueError("No valid agents configured")

    def make_agent_node(name: str):
        async def node(state: AssessmentState) -> dict[str, Any]:
            return await _agent_node(name, resources, state)
        return node

    async def aggregate_node(state: AssessmentState) -> dict[str, Any]:
        return await _aggregate(resources, state)

    builder.add_edge(START, "prepare")
    for name in agents:
        builder.add_node(name, make_agent_node(name))
        builder.add_edge("prepare", name)

    builder.add_node("aggregate", aggregate_node)
    for name in agents:
        builder.add_edge(name, "aggregate")
    builder.add_edge("aggregate", END)
    return builder.compile()


async def run_assessment(
    *,
    config: AIConfig,
    registry: ProviderRegistry,
    rag: MitreRAG,
    gate: AITrustGate,
    founder_request: str,
    evidence: str = "",
    engagement_id: str | None = None,
) -> dict[str, Any]:
    if config.provider != "ollama":
        raise PermissionError("Analysis requires a local loopback provider")
    require_local_http(config.primary.base_url)
    if not engagement_id or not engagement_id.strip():
        raise PermissionError("An independently authorized engagement is required")
    resources = _Resources(config=config, registry=registry, rag=rag, gate=gate)
    if not rag.ready:
        await rag.build()

    graph = _build_assessment_graph(resources)
    result = await graph.ainvoke({
        "founder_request": founder_request,
        "evidence": evidence,
        "engagement_id": engagement_id,
        "provider": config.provider,
        "top_k": config.mitre.top_k,
        "agent_results": [],
        "trustgate_decisions": [],
        "errors": [],
    })
    response = {
        "engagement_id": engagement_id,
        "trustgate_decisions": result["trustgate_decisions"],
    }
    if "consolidated" not in result:
        return {**response, "status": "withheld"}
    return {**response, "status": "completed",
            "agent_results": result["agent_results"], "consolidated": result["consolidated"]}
