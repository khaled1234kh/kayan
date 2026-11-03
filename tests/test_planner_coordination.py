"""Controlled coordinator tests: no model, gate service or target execution."""
from types import SimpleNamespace
import pytest
from pentagi import live_engagement as live
from pentagi.agents.reporting_agent import ReportingAgent

ROLES = ['recon_agent', 'webapp_agent', 'network_agent', 'reporting_agent']

def test_authorization_activity_uses_readable_unicode_separator():
    e=object.__new__(live.LiveEngagement)
    e.engagement_id='text-regression'
    decision=SimpleNamespace(allowed=True,decision='ALLOW',reason='Scoped permit',audit_entry_id='audit',policy_id='policy')
    e.trustgate=SimpleNamespace(authorize=lambda *a:decision)
    captured=[]
    e._record_activity=lambda agent,kind,task,content,details:captured.append(content)
    agent=SimpleNamespace(agent_id='planner',role='planner_agent')
    assert e._authorize(agent,'llm_inference',{'purpose':'coordinate'}) is decision
    assert captured==['ALLOW: llm_inference \u2014 Scoped permit']

def harness(monkeypatch, roles=ROLES, failure=None):
    e = object.__new__(live.LiveEngagement)
    e.engagement_id = 'unit-coordination'
    e.planner = live.ReasoningAgent('planner', 'planner_agent', e.engagement_id, None)
    e.agents = [live.ReasoningAgent(r, r, e.engagement_id, None) for r in ROLES[:3]]
    e.reporting_agent = ReportingAgent(e.engagement_id)
    e.agent_states = {a.agent_id: {'status':'idle','current_task':None,'activity':'Standing by','findings_count':0} for a in [e.planner,*e.agents,e.reporting_agent]}
    e.findings=[];e.transcript=[];e.report=None;e.grounding_enabled=False;e.status='ready'
    e.llm=SimpleNamespace(model='qwen2.5:7b');e.roe={}
    e._push_console_state=lambda:None
    e._instructions=lambda a:[]
    e._context=lambda a,t,d: {'task_context':d}
    e._route=lambda *args:None
    e._authorize=lambda *args,**kw:SimpleNamespace(allowed=True)
    e.trustgate=SimpleNamespace(get_audit_entries=lambda n:[])
    closed=[];monkeypatch.setattr(live,'LabTools',lambda target:SimpleNamespace(close=lambda:closed.append(True)))
    calls=[];contexts=[]
    def model(a,p,c,shape):
        contexts.append((a.role,c))
        if shape is live.Plan:return live.Plan(assignments=[live.Assignment(role=r,task='Inspect owned lab') for r in roles])
        return live.ReportSummary(summary='Controlled summary',finding_ids=[],recommendations=[])
    e._model_call=model
    def specialist(a,task):
        calls.append((a.role,e.agent_states['planner']['status']))
        if a.role==failure:raise live.SpecialistRecoveryExhausted('bounded test failure')
        return live.SpecialistResult([], {'complete':True,'successful_tools':[], 'untested_tools':[],
            'tool_errors':[], 'verification_issues':[], 'stop_reason':'catalogue_exhausted'})
    e._specialist=specialist
    monkeypatch.setattr(e.reporting_agent,'save_report',lambda *args:('unit.json','unit.md'))
    return e,calls,contexts,closed


def test_planner_remains_working_until_reporting_finishes(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    report=e.run()
    assert [r for r,s in calls]==ROLES[:3]
    assert all(s=='working' for r,s in calls)
    assert e.agent_states['planner']['status']=='completed'
    assert report['assessment_completion']['complete'] is True
    assert len(report['assessment_completion']['specialist_outcomes'])==3
    assert closed==[True]


def test_specialist_failure_continues_to_reporting_with_explicit_partial_coverage(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch,failure='webapp_agent')
    report=e.run()
    assert [r for r,s in calls]==ROLES[:3]
    assert e.agent_states['webapp_agent']['status']=='blocked'
    assert e.agent_states['planner']['status']=='completed'
    assert report['assessment_completion']['complete'] is False
    assert report['assessment_completion']['specialist_outcomes'][1]['status']=='failed'
    assert 'incomplete' in report['assessment_completion']['notice'].lower()
    assert contexts[-1][1]['task_context']['specialist_outcomes'][1]['status']=='failed'
    assert closed==[True]


@pytest.mark.parametrize('roles',[
 ['network_agent','webapp_agent','recon_agent','reporting_agent'],
 ['recon_agent','recon_agent','network_agent','reporting_agent'],
 ['reporting_agent','recon_agent','webapp_agent','network_agent'],
])
def test_invalid_dependency_order_never_dispatches(monkeypatch,roles):
    e,calls,contexts,closed=harness(monkeypatch,roles=roles)
    with pytest.raises(RuntimeError,match='roster/dependency'):e.run()
    assert calls==[] and e.status=='failed'
    assert e.agent_states['planner']['status']=='blocked'
    assert closed==[True]


def test_reporting_failure_marks_coordinator_failed_not_completed(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    monkeypatch.setattr(e.reporting_agent,'save_report',lambda *a:(_ for _ in ()).throw(OSError('disk unavailable')))
    with pytest.raises(OSError):e.run()
    assert e.status=='failed' and e.report is None
    assert e.agent_states['planner']['status']=='blocked'
    assert closed==[True]


def test_partial_report_markdown_keeps_coverage_warning():
    reporter=ReportingAgent('unit')
    report=reporter.generate_report([], 'owned lab', 'unit')
    report['assessment_completion']={'complete':False,'notice':'Incomplete assessment: Web-App failed',
        'specialist_outcomes':[{'role':'webapp_agent','status':'failed','error':'bounded stop'}]}
    text=reporter.to_markdown(report)
    assert 'Incomplete assessment' in text and 'bounded stop' in text


def test_planner_panel_state_has_coordination_task_and_tier(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    captured=[]
    e._push_console_state=lambda:captured.append(dict(e.agent_states['planner']))
    e.run()
    assert any(s.get('current_task','').startswith('Assigning recon_agent') for s in captured if s.get('current_task'))
    assert all(t['model_tier']=='A' for t in e.transcript if t['agent_role']=='planner_agent')
    assert [t['specialist_outcome']['role'] for t in e.transcript if t['kind']=='specialist_outcome']==ROLES[:3]


def test_saved_option_b_preserves_partial_assessment_notice():
    import json,uuid
    from pathlib import Path
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from console.backend.planning_api import install_planning_api
    eid=str(uuid.uuid4())
    report=ReportingAgent(eid).generate_report([], 'owned lab', eid)
    report['assessment_completion']={'complete':False,'notice':'Incomplete assessment',
        'specialist_outcomes':[{'role':'webapp_agent','status':'failed','error':'controlled stop'}]}
    path=Path('reports')/f'report_{eid[:8]}.json'
    assert not path.exists()
    path.write_text(json.dumps(report),encoding='utf-8')
    try:
        app=FastAPI();install_planning_api(app,lambda:{'engagement_id':eid,'status':'completed','execution_engine':'local_llm'})
        with TestClient(app) as client:
            assert client.post('/planning/risk-plan',json={'engagement_context':{'infrastructure_summary':'public web application'}}).status_code==200
            assert client.post('/planning/direct-mitigation',json={'engagement_context':{'infrastructure_summary':'public web application'}}).status_code==200
            response=client.get('/planning/current-mitigation')
            assert response.status_code==200
            assert response.json()['assessment_completion']==report['assessment_completion']
    finally:
        path.unlink()


def test_one_invalid_plan_can_be_corrected_without_fabricated_assignments(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    base=e._model_call;attempts=[]
    def model(a,p,c,shape):
        if shape is live.Plan:
            attempts.append(p)
            if len(attempts)==1:
                return live.Plan(assignments=[live.Assignment(role=r,task='Inspect owned lab') for r in reversed(ROLES)])
        return base(a,p,c,shape)
    e._model_call=model
    e.run()
    assert len(attempts)==2 and len(calls)==3
    assert any(t['kind']=='plan_rejected' for t in e.transcript)


def test_report_gate_denial_never_saves_and_blocks_coordinator(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    saved=[]
    e._authorize=lambda *a,**kw:SimpleNamespace(allowed=False)
    monkeypatch.setattr(e.reporting_agent,'save_report',lambda *a:saved.append(True))
    with pytest.raises(RuntimeError,match='denied report writing'):e.run()
    assert saved==[] and e.agent_states['planner']['status']=='blocked'


def test_planner_consumes_queued_guidance_at_specialist_boundaries(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    n=0
    def instructions(a):
        nonlocal n
        if a is e.planner:
            n+=1
            if n==4:return [{'instruction':'Keep remaining checks read-only','audit_entry_id':'controlled-instruction'}]
        return []
    e._instructions=instructions
    e.run()
    revised=[c for role,c in contexts if c['task_context'].get('completed_outcomes')]
    assert revised and revised[0]['task_context']['operator_instructions'][0]['audit_entry_id']=='controlled-instruction'
    assert len(calls)==3


def test_planner_session_exposes_coordinated_findings_without_changing_owner(monkeypatch):
    from console.backend import main
    from fastapi.testclient import TestClient
    finding={'id':'f1','agent':'webapp_agent','type':'xss','mitre':'T1190'}
    monkeypatch.setattr(main,'_engagement_state',{'engagement_id':'unit','agents':[
        {'agent_id':'p','role':'planner_agent'}, {'agent_id':'w','role':'webapp_agent'}],
        'findings':[finding],'transcript':[]})
    with TestClient(main.app) as client:
        data=client.get('/agents/p/session?engagement_id=unit').json()
        assert data['findings']==[finding] and data['findings_scope']=='coordinated_assessment'
        assert client.get('/agents/w/session?engagement_id=unit').json()['findings']==[finding]


def test_invalid_boundary_revision_does_not_relabel_completed_specialist_as_failed(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    count=0
    def instructions(a):
        nonlocal count
        if a is e.planner:
            count+=1
            if count==4:return [{'instruction':'bounded update','audit_entry_id':'unit'}]
        return []
    base=e._model_call
    def model(a,p,c,shape):
        plan=base(a,p,c,shape)
        if c['task_context'].get('completed_outcomes'):plan.assignments[0].task='Attempt to rewrite completed work'
        return plan
    e._instructions=instructions;e._model_call=model
    with pytest.raises(RuntimeError,match='completed work cannot be changed'):e.run()
    assert e.agent_states['recon_agent']['status']=='completed'
    assert e.agent_states['planner']['status']=='blocked'


@pytest.mark.parametrize('ids', [[], ['known', 'known'], ['invented']])
def test_reporting_cannot_silently_omit_duplicate_or_invent_verified_ids(monkeypatch, ids):
    e,calls,contexts,closed=harness(monkeypatch)
    e.findings=[{'id':'known','type':'xss','mitre':'T1190','agent':'webapp_agent','verified':True}]
    base=e._model_call
    e._model_call=lambda a,p,c,shape: (live.ReportSummary(summary='Test',finding_ids=ids,recommendations=[])
        if shape is live.ReportSummary else base(a,p,c,shape))
    saved=[]
    monkeypatch.setattr(e.reporting_agent,'save_report',lambda *args:saved.append(True))
    with pytest.raises(RuntimeError,match='verified finding IDs'):
        e.run()
    assert not saved and e.status=='failed' and closed==[True]


@pytest.mark.parametrize('task', ['     ', '\t\n  '])
def test_whitespace_assignment_is_invalid(task):
    with pytest.raises(ValueError):
        live.Assignment(role='recon_agent',task=task)


def test_plan_rejects_unknown_control_fields():
    with pytest.raises(ValueError):
        live.Plan(assignments=[{'role':r,'task':'Inspect owned lab'} for r in ROLES], bypass_gate=True)


def test_report_omission_can_be_corrected_once_without_fabricating_findings(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    e.findings=[{'id':'known','type':'xss','mitre':'T1190','agent':'webapp_agent','verified':True}]
    base=e._model_call; report_calls=[]
    def model(a,p,c,shape):
        if shape is live.ReportSummary:
            report_calls.append(c)
            return live.ReportSummary(summary='Test',finding_ids=['known'] if len(report_calls)==2 else [],recommendations=[])
        return base(a,p,c,shape)
    e._model_call=model
    report=e.run()
    assert len(report_calls)==2 and report['model_summary']['finding_ids']==['known']
    assert 'validation_feedback' not in report_calls[0]['task_context']
    assert 'validation_feedback' in report_calls[1]['task_context']
    assert [f['id'] for f in e.findings]==['known']


def test_completed_loop_with_untested_tools_flows_to_reporting_and_markdown(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    base=e._specialist
    def specialist(a,task):
        result=base(a,task)
        if a.role=='webapp_agent':result.coverage.update(complete=False,untested_tools=['directory_traversal'],stop_reason='action_budget')
        return result
    e._specialist=specialist
    report=e.run()
    completion=report['assessment_completion']
    assert completion['execution_complete'] is True and completion['complete'] is False
    assert contexts[-1][1]['task_context']['specialist_outcomes'][1]['coverage']['untested_tools']==['directory_traversal']
    assert 'directory_traversal' in e.reporting_agent.to_markdown(report)
    assert 'coverage limitations disclosed' in e.agent_states['planner']['activity']


def test_boundary_revision_can_be_corrected_once_preserving_completed_prefix(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    polls=0
    def instructions(a):
        nonlocal polls
        if a is e.planner:
            polls+=1
            if polls==4:return [{'instruction':'Keep scoped checks','audit_entry_id':'unit'}]
        return []
    e._instructions=instructions
    base=e._model_call; revisions=[]
    def model(a,p,c,shape):
        plan=base(a,p,c,shape)
        if shape is live.Plan and c['task_context'].get('completed_outcomes'):
            revisions.append(c)
            if len(revisions)==1:plan.assignments[0].task='Rewrite completed work'
        return plan
    e._model_call=model
    e.run()
    assert len(revisions)==2 and len(calls)==3
    assert e.agent_states['recon_agent']['status']=='completed'
    assert 'validation_feedback' not in revisions[0]['task_context']


def test_model_inference_denial_does_not_trigger_schema_retry(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    attempts=[]
    def denied(*args):
        attempts.append(True)
        raise RuntimeError('TrustGate denied model inference')
    e._model_call=denied
    with pytest.raises(RuntimeError,match='denied model inference'):e.run()
    assert attempts==[True] and calls==[] and e.status=='failed'


@pytest.mark.parametrize('role,tool',[('webapp_agent','http_probe'),('network_agent','discover_endpoints'),('recon_agent','xss_test')])
def test_cross_role_tool_assignment_never_dispatches(monkeypatch,role,tool):
    e,calls,contexts,closed=harness(monkeypatch)
    base=e._model_call
    def model(a,p,c,shape):
        result=base(a,p,c,shape)
        if shape is live.Plan:
            next(item for item in result.assignments if item.role==role).task=f'Run {tool} on the lab'
        return result
    e._model_call=model
    with pytest.raises(RuntimeError,match='tool catalogue'):e.run()
    assert calls==[] and e.status=='failed'


def test_finished_engine_cannot_rerun_and_reuse_findings_under_old_roe(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    report=e.run()
    with pytest.raises(RuntimeError,match='fresh signed ROE'):e.run()
    assert e.report is report and len(calls)==3 and closed==[True]


def test_reporting_task_may_reference_observed_tools_without_executing_them(monkeypatch):
    e,calls,contexts,closed=harness(monkeypatch)
    base=e._model_call
    def model(a,p,c,shape):
        result=base(a,p,c,shape)
        if shape is live.Plan:result.assignments[-1].task='Summarize xss_test findings and disclose limits'
        return result
    e._model_call=model
    assert e.run()['assessment_completion']['complete'] is True
