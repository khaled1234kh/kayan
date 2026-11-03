"""Repeatable fictional offline planning outputs; separate from live Planner eval."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from pentagi.risk_plan import build_risk_plan
from pentagi.agents.reporting_agent import ReportingAgent


def run(label):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',label):raise ValueError('Use a unique safe label')
    folder=Path('eval/reports')/label;folder.mkdir(exist_ok=False)
    path=Path(__file__).parent/'fixtures/planning_contexts_v2.json'
    cases=json.loads(path.read_text(encoding='utf-8'))
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'pipeline':'Deterministic offline Phase 1 and Option A, not the Qwen multi-agent Planner','cases':[]}
    for case in cases:
        plan=build_risk_plan(case['engagement_context'])
        report=ReportingAgent('fictional-'+case['id']).generate_direct_mitigation(plan)
        (folder/(case['id']+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        recommendations=report['mitigation_plan']['recommendations']
        result['cases'].append({'id':case['id'],'risk_count':len(plan['risks']),
            'references':[risk['reference']['id'] for risk in plan['risks']],
            'risk_titles':[risk['title'] for risk in plan['risks']],
            'recommendation_titles':[r['title'] for r in recommendations],
            'distinct_actions':len({r['action'] for r in recommendations}),
            'context_preserved':plan['context']==case['engagement_context']==report['narrative_context'],
            'target_accessed':plan['target_accessed'] or report['target_accessed'],
            'verified_findings':len(report['findings'])})
    (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--label',required=True)
    run(parser.parse_args().label)
