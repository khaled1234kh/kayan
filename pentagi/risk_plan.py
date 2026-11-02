"""Phase 1: pure local retrieval from descriptions, with no runtime/tool client."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict
from grounding.retrieval import local_index
from pentagi.engagement_context import descriptive_context, CONTEXT_LABEL


class Reference(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    framework: Literal['mitre-attack', 'owasp-top10']
    name: str
    source_url: str
    description: str
    score: float


class HypotheticalRisk(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    priority: int
    title: str
    hypothesis: str
    evidence_basis: Literal['hypothetical_context_match'] = 'hypothetical_context_match'
    verified: Literal[False] = False
    reference: Reference


class RiskPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1] = 1
    kind: Literal['hypothetical_risk_plan'] = 'hypothetical_risk_plan'
    generated_at: str
    context: dict[str, str]
    context_label: str = CONTEXT_LABEL
    ranking_basis: str = 'Descending TF-IDF text relevance, not measured likelihood, impact or vulnerability severity.'
    uncertainty: str = 'Descriptions are unverified. Matches are hypotheses to review, not findings. No target was contacted.'
    target_accessed: Literal[False] = False
    status: Literal['hypotheses_available', 'insufficient_context_or_matches']
    index_built_at: str
    risks: list[HypotheticalRisk]


def build_risk_plan(context=None):
    context = descriptive_context(context)
    index = local_index()  # Existing pinned ATT&CK/OWASP index, never a network fetch.
    matches = index.retrieve(' '.join(context.values()), 'B', limit=3) if context else []
    risks = [HypotheticalRisk(id=f'risk_{i}', priority=i, title=f'Risk {i}: {entry["name"]}',
        hypothesis=f'The supplied description may warrant review of {entry["name"]}; applicability has not been tested.',
        reference=Reference(**{key:entry[key] for key in Reference.model_fields}))
        for i, entry in enumerate(matches, 1)]
    return RiskPlan(generated_at=datetime.now(timezone.utc).isoformat(), context=context,
        status='hypotheses_available' if risks else 'insufficient_context_or_matches',
        index_built_at=index.metadata['built_at'], risks=risks).model_dump()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True, help='UTF-8 JSON containing only the six descriptive fields')
    parser.add_argument('--output', required=True, help='New output file; existing files are refused')
    args = parser.parse_args()
    plan = build_risk_plan(json.loads(Path(args.context).read_text(encoding='utf-8')))
    with Path(args.output).open('x', encoding='utf-8') as file:
        json.dump(plan, file, ensure_ascii=False, indent=2)
