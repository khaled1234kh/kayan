"""Immutable API evidence for offline TA planning; never starts an assessment."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import httpx
from pentagi.agents.reporting_agent import ReportingAgent

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = {'company_size':'25 employees (synthetic evaluation fixture)',
    'departments':'Operations and customer support',
    'infrastructure_summary':'Public web application and API; review SQL injection and broken access control',
    'network_architecture':'Office network and hosted application',
    'data_storage':'Relational database with customer records',
    'customer_touchpoints':'Customer web portal and login'}


def check(label):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',label): raise ValueError('Use a unique safe label')
    out = ROOT/'eval/reports/ta_alignment'/label
    out.mkdir(parents=True,exist_ok=False)
    audit_path = ROOT/'audit_log.jsonl'
    digest = lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    before = digest(audit_path)
    with httpx.Client(base_url='http://127.0.0.1:8001',timeout=30) as client:
        state = client.get('/engagement');state.raise_for_status(); state=state.json()
        assert state.get('status') == 'completed'
        payload = {'engagement_context':CONTEXT}
        risk = client.post('/planning/risk-plan',json=payload);risk.raise_for_status();risk=risk.json()
        direct = client.post('/planning/direct-mitigation',json=payload);direct.raise_for_status();direct=direct.json()
        tested = client.get('/planning/current-mitigation');tested.raise_for_status();tested=tested.json()
        assert direct['findings']==[] and direct['target_accessed'] is False
        assert all(r['verified'] is False for r in risk['risks'])
        assert direct['mitigation_plan']['evidence_basis']=='hypothetical_risk_plan'
        assert tested['mitigation_plan']['evidence_basis']=='verified_findings'
        assert set(direct['mitigation_plan'])==set(tested['mitigation_plan'])
        assert client.post('/planning/risk-plan',json={'engagement_context':{'targets':['outside.example']}}).status_code==422
        assert client.post('/planning/direct-mitigation',json={**payload,'findings':[{'verified':True}]}).status_code==422
        empty = client.post('/planning/risk-plan',json={});empty.raise_for_status()
        assert empty.json()['status']=='insufficient_context_or_matches' and not empty.json()['risks']
        assert client.get('/engagement').json()==state, 'Planning changed the live console state'
    after = digest(audit_path)
    assert before==after, 'Audit changed during offline-only checks; investigate concurrent/live activity'
    for name,data in [('context',CONTEXT),('risk_plan',risk),('option_a',direct),('option_b_saved_run_view',tested)]:
        (out/(name+'.json')).write_bytes(json.dumps(data,ensure_ascii=False,indent=2).encode('utf-8'))
    agent=ReportingAgent('offline-evidence')
    for name,data in [('option_a',direct),('option_b_saved_run_view',tested)]:
        (out/(name+'.md')).write_bytes(agent.to_markdown(data).encode('utf-8'))
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'passed',
        'risk_count':len(risk['risks']), 'option_a_findings':len(direct['findings']),
        'option_a_recommendations':len(direct['mitigation_plan']['recommendations']),
        'option_b_source_engagement':tested['engagement_id'],
        'option_b_verified_findings':tested['mitigation_plan']['verified_finding_count'],
        'option_b_recommendations':len(tested['mitigation_plan']['recommendations']),
        'audit_unchanged':before==after, 'audit_sha256':before, 'console_state_unchanged':True,
        'limits':'Actual local HTTP calls and offline report generation. Option B reuses saved verified findings; no new live assessment, model comparison, mitigation effectiveness, browser click/visual acceptance or actual pricing measurement.'}
    (out/'results.json').write_bytes(json.dumps(result,indent=2).encode())
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--label',required=True)
    check(parser.parse_args().label)
