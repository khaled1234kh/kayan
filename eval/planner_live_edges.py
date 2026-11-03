"""Actual Gate/Qwen/lab fault-path checks, without tool/model mocks.

deny-service adds a real signed-ROE restriction. lab-unavailable requires the
owned lab to be stopped by its operator first; this script never stops services.
Both deliberately submit one tainted authorization request without executing it.
"""
import argparse
import json
from pathlib import Path
import re
import traceback

import httpx
from pentagi.live_engagement import LiveEngagement


def run(label, mode):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', label):
        raise ValueError('Use a unique safe label')
    folder=Path('eval/reports')/label
    folder.mkdir(exist_ok=False)
    result={'label':label,'mode':mode,'passed':False,'mocked_services':False,
        'count_basis':'All engagement Gate decisions except ROE load; one deliberate tainted inference DENY. No operator status/instruction jobs.'}
    engine=None
    try:
        with httpx.Client(timeout=10) as client:
            before=client.get('http://127.0.0.1:8001/engagement').raise_for_status().json()
            if before.get('status') in ('starting','active'):
                raise RuntimeError('Refusing to replace an active assessment')
            (folder/'before-state.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
            if mode=='lab-unavailable':
                try:
                    client.get('http://127.0.0.1:8888/')
                except httpx.ConnectError:
                    pass
                else:
                    raise RuntimeError('lab-unavailable requires the actual owned lab listener to be stopped')
            else:
                client.get('http://127.0.0.1:8888/').raise_for_status()
            audit_before=client.get('http://127.0.0.1:8000/audit/verify').raise_for_status().json()
            assert audit_before['valid'],audit_before
            engine=LiveEngagement()
            engine.create_engagement('Owned-lab real failure-path verification',
                forbidden_actions=['service_scan'] if mode=='deny-service' else [])
            denied=engine._authorize(engine.planner,'llm_inference',{'purpose':'Deliberate tainted target-origin test'},untrusted=True)
            assert not denied.allowed
            report=engine.run()
            eid=engine.engagement_id
            rows=client.get('http://127.0.0.1:8000/audit',params={'limit':10000}).raise_for_status().json()['entries']
            decisions=[r for r in rows if r['engagement_id']==eid and r['tool_name']!='roe_load']
            if mode=='deny-service':
                service_denials=[r for r in decisions if r['tool_name']=='service_scan' and r['decision']=='DENY']
                assert service_denials,'No actual service-scan policy denial observed'
                assert not any(e['kind']=='tool_started' and e.get('tool_name')=='service_scan' for e in engine.transcript)
                assert any('service_scan' in o['coverage']['denied_tools'] for o in report['assessment_completion']['specialist_outcomes'])
            else:
                assert not engine.findings,'Unavailable lab produced findings'
                assert any(e['error'] for e in report['execution_ledger']),'No actual executor errors recorded'
            assert not report['assessment_completion']['complete']
            assert sorted(report['model_summary']['finding_ids'])==sorted(f['id'] for f in engine.findings)
            assert len(report['coordination_reviews'])==3
            assert not any(e['kind']=='tool_started' and e['agent_role']=='planner_agent' for e in engine.transcript)
            view=client.get('http://127.0.0.1:8001/planning/current-mitigation').raise_for_status().json()
            for key in ('coordination_reviews','execution_ledger','governance','assessment_completion'):
                assert view[key]==report[key],key
            audit_after=client.get('http://127.0.0.1:8000/audit/verify').raise_for_status().json()
            assert audit_after['valid']
            result.update(passed=True,engagement_id=eid,findings=len(engine.findings),
                allowed=sum(r['decision']=='ALLOW' for r in decisions),denied=sum(r['decision']=='DENY' for r in decisions),
                assessment_completion=report['assessment_completion'],coordination_reviews=report['coordination_reviews'],
                execution_errors=sum(bool(e['error']) for e in report['execution_ledger']),
                execution_ledger_entries=len(report['execution_ledger']),audit_before=audit_before,audit_after=audit_after,
                option_b_preserved_source_records=True)
    except BaseException as error:
        result.update(error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        if engine:
            (folder/'transcript.json').write_text(json.dumps(engine.transcript,indent=2),encoding='utf-8')
            engine.close()
        (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    parser.add_argument('--mode',choices=['deny-service','lab-unavailable'],required=True)
    args=parser.parse_args()
    run(args.label,args.mode)
