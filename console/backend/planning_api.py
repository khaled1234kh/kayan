"""Offline planning/report views, deliberately independent of the live runtime."""
from pathlib import Path
import json
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from pentagi.engagement_context import EngagementContext
from pentagi.risk_plan import build_risk_plan
from pentagi.agents.reporting_agent import ReportingAgent


class PlanningRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    engagement_context: EngagementContext = Field(default_factory=EngagementContext)


def install_planning_api(app, get_state):
    @app.post('/planning/risk-plan')
    def risk_plan(payload: PlanningRequest):
        return build_risk_plan(payload.engagement_context)

    @app.post('/planning/direct-mitigation')
    def direct_mitigation(payload: PlanningRequest):
        # Compute the plan here: client-supplied findings/reference URLs are not accepted.
        plan = build_risk_plan(payload.engagement_context)
        return ReportingAgent(str(uuid.uuid4())).generate_direct_mitigation(plan)

    @app.get('/planning/current-mitigation')
    def current_mitigation():
        state = get_state()
        if state.get('status') != 'completed' or state.get('execution_engine') != 'local_llm':
            raise HTTPException(409, 'A completed actual-model assessment is required for Option B')
        try:
            eid = str(uuid.UUID(state['engagement_id']))
        except (KeyError, ValueError):
            raise HTTPException(409, 'Current assessment ID is invalid')
        path = Path(__file__).resolve().parents[2]/'reports'/f'report_{eid[:8]}.json'
        if not path.is_file():
            raise HTTPException(409, 'Saved assessment report is unavailable')
        source = json.loads(path.read_text(encoding='utf-8'))
        if source.get('engagement_id') != eid:
            raise HTTPException(409, 'Saved report ID does not match the current assessment')
        # Derive a view without overwriting historical reports or running any target tool.
        findings = [{**f, 'mitre':f.get('mitre_id', f.get('mitre', 'Unknown')),
            'data':f.get('evidence', f.get('data', {}))} for f in source['findings']]
        report = ReportingAgent(eid).generate_report(findings, source['target'], eid,
            source.get('narrative_context'))
        if source.get('assessment_completion'):
            report['assessment_completion'] = source['assessment_completion']
        for key in ('coordination_reviews', 'execution_ledger', 'governance', 'model_summary'):
            if key in source:
                report[key] = source[key]
        report['source_generated_at'] = source.get('generated_at')
        report.update(option='B', execution_engine='offline_report_view',
            source_report=str(path.relative_to(path.parents[1])),
            evidence_label='Verified findings supplied by the saved governed run; this view performs no new testing.')
        return report
