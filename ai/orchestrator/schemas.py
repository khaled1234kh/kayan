"""Strict output schemas and deterministic validation for agent responses.

An LLM may *propose* a MITRE mapping; only a deterministic check against the
downloaded ATT&CK catalogue decides whether that ID is admissible. This keeps
hallucinated technique IDs out of evidence records.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class Finding(BaseModel):
    technique_id: str = Field(default="", description="MITRE ATT&CK ID, e.g. T1059.001")
    tactic: str = ""
    claim: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: str = "low"
    assumptions: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    agent: str
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class ConsolidatedAssessment(BaseModel):
    executive_summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_citations: list[str] = Field(default_factory=list)


_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _candidate_json_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for match in _FENCE.finditer(text):
        blocks.append(match.group(1))
    blocks.append(text.strip())
    first, last = text.find("{"), text.rfind("}")
    if 0 <= first < last:
        blocks.append(text[first : last + 1])
    return blocks


def parse_agent_result(text: str, *, agent: str, known_ids: set[str] | None = None) -> AgentResult:
    """Parse JSON defensively; never let malformed model output crash a node."""
    payload: dict[str, Any] | None = None
    for candidate in _candidate_json_blocks(text):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                payload = parsed
                break
        except (json.JSONDecodeError, TypeError):
            continue
    if payload is None:
        return AgentResult(agent=agent, summary=text.strip()[:1500])

    payload.setdefault("agent", agent)
    try:
        result = AgentResult.model_validate(payload)
    except ValidationError:
        return AgentResult(agent=agent, summary=text.strip()[:1500])

    if known_ids is not None:
        for finding in result.findings:
            if finding.technique_id and finding.technique_id not in known_ids:
                finding.assumptions.append(
                    f"Unverified technique ID {finding.technique_id} removed by deterministic validation"
                )
                finding.technique_id = ""
    return result
