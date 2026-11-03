"""Real coordinator acceptance over the existing live harness; starts an owned-lab run.

Keeps a separate WebSocket observer to verify transient coordination states.
No model/tool/gate mock, policy edits, alternative authority or simulated fallback.
"""
import argparse
import asyncio
import json
from pathlib import Path
import re
import traceback

import httpx
import websockets

from eval.live_runtime_check import check

BASE = 'http://127.0.0.1:8001'
ORDER = ['recon_agent','webapp_agent','network_agent','reporting_agent']

async def run(label):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',label):raise ValueError('Use a unique safe label')
    folder=Path('eval/reports')/label
    folder.mkdir(exist_ok=False)
    async with httpx.AsyncClient(timeout=20) as client:
        audit_before=(await client.get('http://127.0.0.1:8000/audit/verify')).raise_for_status().json()
        assert audit_before.get('valid') is True,audit_before
        before=(await client.get(BASE+'/engagement')).raise_for_status().json()
        (folder/'before-state.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
        old_id=before.get('engagement_id');ready=asyncio.Event();observed=[]
        final=None
        async def watch():
            nonlocal final
            async with websockets.connect('ws://127.0.0.1:8001/ws',max_size=16*1024*1024) as socket:
                ready.set()
                async for raw in socket:
                    state=json.loads(raw)['data']
                    if state.get('engagement_id')==old_id:continue
                    final=state
                    agents=state.get('agents',[])
                    observed.append({'engagement_id':state.get('engagement_id'),'status':state.get('status'),
                        'entries':len(state.get('transcript',[])),
                        'agents':[{k:a.get(k) for k in ['role','status','current_task','model_tier','model_name']} for a in agents]})
                    if state.get('status') in ('failed','completed'):return
        observer=asyncio.create_task(watch())
        await asyncio.wait_for(ready.wait(),10)
        result={'label':label,'passed':False}
        try:
            live=await check(True,label=label)
            await asyncio.wait_for(observer,10)
            final=(await client.get(BASE+'/engagement')).raise_for_status().json()
            assert final['engagement_id']==live['engagement_id']
            transcript=final['transcript']
            assignments=[e['assigned_role'] for e in transcript if e.get('assigned_role')]
            assert assignments==ORDER,assignments
            outcomes=[e['specialist_outcome'] for e in transcript if e['kind']=='specialist_outcome']
            assert [o['role'] for o in outcomes]==ORDER[:3]
            assert all(o['status']=='completed' for o in outcomes),outcomes
            from pentagi.lab_tools import ROLE_TOOLS
            # These are semantic coordination checks, separate from transport or pixels.
            import re as regex
            known_tools={tool for tools in ROLE_TOOLS.values() for tool in tools}
            for entry in [e for e in transcript if e.get('assigned_role')]:
                role=entry['assigned_role']
                mentioned=set(regex.findall(r'[a-z][a-z0-9_]*',entry['content'].lower())) & known_tools
                if role in ROLE_TOOLS:assert mentioned <= set(ROLE_TOOLS[role]),entry
            for outcome in outcomes:
                coverage=outcome['coverage']
                catalogue=set(ROLE_TOOLS[outcome['role']])
                assert set(coverage['attempted_tools'])|set(coverage['untested_tools'])==catalogue,coverage
                assert not set(coverage['attempted_tools']) & set(coverage['untested_tools']),coverage
                assert set(coverage['successful_tools']) <= set(coverage['attempted_tools']),coverage
                assert coverage['complete']==(not any(coverage[key] for key in ('untested_tools','tool_errors','verification_issues','denied_tools'))),coverage
            report_path=__import__('pathlib').Path('reports')/f"report_{live['engagement_id'][:8]}.json"
            saved_report=json.loads(report_path.read_text(encoding='utf-8'))
            assert saved_report['assessment_completion']['complete']==all(o['coverage']['complete'] for o in outcomes)
            finding_ids=[f['id'] for f in final['findings']]
            assert sorted(saved_report['model_summary']['finding_ids'])==sorted(finding_ids)
            active_frames=[]
            for frame in observed:
                if frame['engagement_id']!=live['engagement_id']:continue
                if any(a['role'] in ORDER and a['status']=='working' for a in frame['agents']):
                    planner=next(a for a in frame['agents'] if a['role']=='planner_agent')
                    assert planner['status']=='working',frame
                    active_frames.append(frame)
            assert active_frames,'No live specialist-active coordination frame observed'
            completed=[e['agent_role'] for e in transcript if e['kind']=='agent_completed']
            assert completed[-1]=='planner_agent',completed
            assert not any(e['agent_role']=='planner_agent' and e['kind']=='tool_started' for e in transcript)
            assert live['models']==['qwen2.5:7b'],live['models']
            audit=(await client.get('http://127.0.0.1:8000/audit',params={'limit':10000})).raise_for_status().json()['entries']
            planner_rows=[r for r in audit if r['engagement_id']==live['engagement_id'] and r['agent_role']=='planner_agent']
            assert planner_rows and all(r['tool_name'] in ('llm_inference','message_send') for r in planner_rows)
            audit_after=(await client.get('http://127.0.0.1:8000/audit/verify')).raise_for_status().json()
            assert audit_after.get('valid') is True,audit_after
            result.update(passed=True,engagement_id=live['engagement_id'],findings=live['findings'],allowed=live['allowed'],denied=live['denied'],
                assignment_order=assignments,specialist_outcomes=outcomes,observed_active_frames=len(active_frames),
                planner_last_completed=True,planner_has_no_tool_dispatch=True,models=live['models'],
                incremental_output_verified=live['incremental_output_verified'],visual_verification=False,
                audit_before=audit_before,audit_after=audit_after)
            result.update(catalogue_coverage_accounting_verified=True,role_tool_assignments_verified=True,
                report_finding_ids_complete=True,assessment_completion=saved_report['assessment_completion'])
        except BaseException as error:
            result.update(error=repr(error),traceback=traceback.format_exc())
            raise
        finally:
            if not observer.done():observer.cancel()
            try:await observer
            except asyncio.CancelledError:pass
            if final:(folder/'final-state.json').write_text(json.dumps(final,indent=2),encoding='utf-8')
            (folder/'websocket-observations.json').write_text(json.dumps(observed,indent=2),encoding='utf-8')
            (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
    asyncio.run(run(args.label))
