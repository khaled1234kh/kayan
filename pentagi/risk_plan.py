"""Phase 1: pure local retrieval from descriptions, with no runtime/tool client."""
import argparse
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from grounding.retrieval import local_index
from pentagi.engagement_context import descriptive_context, CONTEXT_LABEL
from pentagi.contextual_planning import contextual_candidates


class Reference(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    framework: Literal['mitre-attack', 'owasp-top10']
    name: str
    source_url: str
    description: str
    score: float | None = None  # Version-1 text similarity; never risk severity/priority.


class HypotheticalRisk(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    priority: int | None = None  # Legacy v1 only; v2 uses explicit relevance_rank.
    relevance_rank: int | None = None
    title: str
    hypothesis: str
    evidence_basis: Literal['hypothetical_context_match'] = 'hypothetical_context_match'
    verified: Literal[False] = False
    reference: Reference
    scenario_id: str | None = None
    why_relevant: str = ''
    assumptions: str = ''
    assets: list[str] = Field(default_factory=list)
    context_evidence: list[dict] = Field(default_factory=list)
    relevance_score: float | None = None
    relevance_basis: str = ''
    severity: Literal['not_assessed'] = 'not_assessed'
    impact: Literal['not_assessed'] = 'not_assessed'
    likelihood: Literal['not_assessed'] = 'not_assessed'
    mitigation_urgency: Literal['not_assessed'] = 'not_assessed'
    control_actions: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)


class RiskPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1,2] = 2
    kind: Literal['hypothetical_risk_plan'] = 'hypothetical_risk_plan'
    generated_at: str
    context: dict[str, str]
    context_label: str = CONTEXT_LABEL
    ranking_basis: str = 'Context applicability/relevance order from named technical signals and explicitly described control gaps; not measured likelihood, impact, severity or mitigation urgency. TF-IDF is diagnostic text similarity only.'
    uncertainty: str = 'Descriptions are unverified. Matches are hypotheses to review, not findings. No target was contacted.'
    target_accessed: Literal[False] = False
    status: Literal['hypotheses_available', 'insufficient_context_or_matches']
    index_built_at: str
    risks: list[HypotheticalRisk]
    context_integrity: dict = Field(default_factory=dict)
    selection_method: str = 'Version-2 authored scenario requirements with local pinned framework references; no LLM.'
    filtered_text_matches: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    supported_scenario_count: int = 0
    additional_supported_scenarios: list[dict] = Field(default_factory=list)


def build_risk_plan(context=None):
    context = descriptive_context(context)
    index = local_index()  # Existing pinned ATT&CK/OWASP index, never a network fetch.
    candidates = contextual_candidates(context,index) if context else []
    risks = [HypotheticalRisk(id='risk_'+entry['scenario_id'],relevance_rank=i,
        **{key:value for key,value in entry.items() if key!='hypothesis'},hypothesis=entry['hypothesis'])
        for i,entry in enumerate(candidates[:3],1)]
    selected={risk.reference.id for risk in risks}
    supported={item['reference']['id'] for item in candidates}
    diagnostics=index.retrieve(' '.join(context.values()),'B',limit=3) if context else []
    raw=json.dumps(context,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return RiskPlan(generated_at=datetime.now(timezone.utc).isoformat(), context=context,
        status='hypotheses_available' if risks else 'insufficient_context_or_matches',
        index_built_at=index.metadata['built_at'], risks=risks,
        context_integrity={'algorithm':'sha256','canonicalization':'UTF-8 JSON, sorted field names, compact separators; blank optional fields omitted; entered text preserved exactly',
            'sha256':hashlib.sha256(raw).hexdigest(),'field_characters':{k:len(v) for k,v in context.items()}},
        supported_scenario_count=len(candidates),
        additional_supported_scenarios=[{'scenario_id':item['scenario_id'],'title':item['title'],
            'reason':'Outside the three displayed context-relevance suggestions; not a lower-severity judgment.'} for item in candidates[3:]],
        filtered_text_matches=[{'id':m['id'],'name':m['name'],'text_similarity':m['score'],
            'reason':'A context scenario supports this reference, but it is outside the three displayed suggestions; this is not a severity comparison.' if m['id'] in supported else
                'Text similarity alone does not establish applicability; the required technical details for a supported scenario are absent.'}
            for m in diagnostics if m['id'] not in selected],
        limitations=['Authored rules cover a bounded set of scenarios, not a comprehensive company risk assessment.',
            'Descriptions and stated control gaps are unverified. Missing details do not establish missing controls.',
            'Fewer than three supported scenarios is a valid result; no weak matches are added to fill slots.']
        +(['No supported technical scenario: describe the relevant assets, interfaces, trust boundaries or specific control concerns.'] if not risks else [])).model_dump(exclude_none=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True, help='UTF-8 JSON containing only the six descriptive fields')
    parser.add_argument('--output', required=True, help='New output file; existing files are refused')
    args = parser.parse_args()
    plan = build_risk_plan(json.loads(Path(args.context).read_text(encoding='utf-8')))
    with Path(args.output).open('x', encoding='utf-8') as file:
        json.dump(plan, file, ensure_ascii=False, indent=2)
