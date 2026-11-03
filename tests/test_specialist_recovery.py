"""Recovery safety checks with controlled proposals; not real-model evidence."""
import json
from types import SimpleNamespace

import pytest

from integration.trustgate_client import AuthorizationResult
from pentagi.inference_context import model_messages
from pentagi.lab_tools import ROLE_TOOLS
from pentagi.live_engagement import Decision, LiveEngagement, ReasoningAgent, SpecialistRecoveryExhausted


class Gate:
    def __init__(self, denied=()):
        self.denied = set(denied)
        self.calls = []

    def authorize(self, *args, **kwargs):
        tool = args[3] if args else kwargs['tool_name']
        provenance = args[7] if args else kwargs.get('provenance', {})
        self.calls.append(tool)
        allowed = tool not in self.denied and tool in {'port_scan','service_scan','verify_xss'} and 'untrusted' not in provenance.values()
        return AuthorizationResult(allowed, 'ALLOW' if allowed else 'DENY', 'controlled gate decision', 'unit-policy', 'unit-audit')


def harness(proposals, denied=(), role='network_agent'):
    gate = Gate(denied)
    agent = ReasoningAgent('unit-agent', role, 'unit-engagement', gate)
    engagement = object.__new__(LiveEngagement)
    engagement.engagement_id = 'unit-engagement'
    engagement.trustgate = gate
    engagement.target = 'http://127.0.0.1:8888'
    engagement.llm = SimpleNamespace(config={'max_actions_per_specialist':3, 'max_action_retries':2})
    engagement.agent_states = {agent.agent_id:{'status':'idle','findings_count':0}}
    engagement.findings = []
    engagement.transcript = []
    engagement._push_console_state = lambda: None
    engagement._instructions = lambda agent: []
    engagement._context = lambda agent, task, details: {'task_context':details}
    contexts = []
    sequence = iter(proposals)
    def model(agent, purpose, context, shape):
        contexts.append(json.loads(json.dumps(context['task_context'])))
        proposal = next(sequence)
        return Decision(tool=proposal, purpose='controlled test') if isinstance(proposal,str) else proposal
    engagement._model_call = model
    executed = []
    def run(tool, verification=False):
        executed.append(tool)
        return {'open_ports':[8888]}
    engagement.tools = SimpleNamespace(run=run)
    agent.event_sink = engagement._record_activity
    return engagement, agent, gate, contexts, executed


def test_unknown_skill_id_is_audited_and_feedback_recovers_to_registered_action():
    slug = 'testing-for-xss-vulnerabilities-with-burpsuite'
    e,a,gate,contexts,executed = harness([slug,'port_scan','finish'])
    e._specialist(a,'Inspect the lab')
    assert executed == ['port_scan'] and gate.calls == [slug,'port_scan']
    feedback = contexts[1]['action_feedback'][0]
    assert feedback['gate_decision'] == 'DENY' and feedback['audit_entry_id'] == 'unit-audit'
    assert contexts[1]['action_space']['callable_tools'] == ROLE_TOOLS[a.role]+['finish']
    assert e.findings == []


def test_repeated_proposal_never_dispatches_twice_and_next_turn_excludes_it():
    e,a,gate,contexts,executed = harness(['port_scan','port_scan','service_scan'])
    e._specialist(a,'Inspect the lab')
    assert executed == ['port_scan','service_scan']
    assert gate.calls.count('port_scan') == 1
    assert contexts[2]['action_space']['callable_tools'] == ['service_scan','finish']
    assert 'already attempted' in contexts[2]['action_feedback'][0]['reason']


def test_registered_gate_denial_does_not_execute_and_can_choose_different_tool():
    e,a,gate,contexts,executed = harness(['port_scan','service_scan'], denied=['port_scan'])
    e._specialist(a,'Inspect the lab')
    assert executed == ['service_scan'] and len(a.denied_actions) == 1
    assert contexts[1]['action_space']['callable_tools'] == ['service_scan','finish']
    assert contexts[1]['action_feedback'][0]['gate_decision'] == 'DENY'


def test_out_of_scope_proposal_never_changes_executor_target():
    e,a,gate,contexts,executed = harness([Decision(tool='port_scan',purpose='bad target',target='192.0.2.55'),'port_scan','finish'])
    e._specialist(a,'Inspect the lab')
    assert executed == ['port_scan']
    assert contexts[1]['action_feedback'][0]['proposed_target'] == '192.0.2.55'
    assert contexts[1]['action_feedback'][0]['gate_decision'] == 'DENY'
    assert e.target == 'http://127.0.0.1:8888'


def test_persistent_confusion_exhausts_two_retries_without_fallback_execution():
    e,a,gate,contexts,executed = harness(['unknown']*3)
    with pytest.raises(SpecialistRecoveryExhausted,match='3 rejected proposals; 2 retries exhausted'):
        e._specialist(a,'Inspect the lab')
    assert len(contexts) == 3 and executed == [] and e.findings == []
    assert e.transcript[-1]['kind'] == 'recovery_exhausted'


def test_gate_allow_does_not_make_private_verifier_a_model_callable_tool():
    e,a,gate,contexts,executed = harness(['verify_xss','finish'],role='webapp_agent')
    e._specialist(a,'Inspect the lab')
    assert executed == []
    assert contexts[1]['action_feedback'][0]['gate_decision'] == 'ALLOW'
    assert 'not registered' in contexts[1]['action_feedback'][0]['reason']
    assert not any(t['kind'] == 'tool_denied' for t in e.transcript)


def test_task_boundary_instructions_survive_recovery_turns():
    e,a,gate,contexts,executed = harness(['unknown','port_scan','finish'])
    batches = iter([[{'instruction':'Keep scope unchanged','audit_entry_id':'instruction-audit'}],[],[]])
    e._instructions = lambda agent: next(batches)
    e._specialist(a,'Inspect the lab')
    assert all(c['governed_operator_instructions'][0]['audit_entry_id'] == 'instruction-audit' for c in contexts)


def test_retrieval_is_read_only_knowledge_not_an_executable_slug_list():
    slug = 'testing-for-xss-vulnerabilities-with-burpsuite'
    context = {'skill_packets':'existing curated background',
        'library_skill_packets':[{'id':slug,'name':'Testing XSS with Burp Suite','body_excerpt':'Background about browser request testing.'}],
        'grounding':[{'id':'T1190','name':'Exploit Public-Facing Application','description':'Knowledge of application exploitation.'}],
        'task_context':{'action_space':{'callable_tools':['xss_test','finish']}}}
    messages = model_messages('webapp_agent','A','Inspect',{},context)
    user = json.loads(messages[1]['content'])
    assert slug not in messages[1]['content'] and context['library_skill_packets'][0]['id'] == slug
    assert 'NO executable actions' in user['read_only_reference_material']['usage']
    assert user['task_context']['action_space']['callable_tools'] == ['xss_test','finish']
    assert 'ONLY callable names' in messages[0]['content']


def test_invalid_retry_configuration_cannot_create_unbounded_recovery():
    e,a,gate,contexts,executed = harness([])
    e.llm.config['max_action_retries'] = 999
    with pytest.raises(ValueError,match='from 0 to 3'):
        e._specialist(a,'Inspect')
    assert contexts == executed == []


def test_early_finish_reports_untested_catalogue_instead_of_full_coverage():
    e,a,gate,contexts,executed = harness(['finish'])
    result=e._specialist(a,'Inspect the lab')
    assert result.coverage['complete'] is False
    assert result.coverage['stop_reason']=='model_finished'
    assert result.coverage['untested_tools']==ROLE_TOOLS[a.role]
    assert not executed


def test_swallowed_executor_error_is_explicit_in_coverage_and_model_context():
    e,a,gate,contexts,executed = harness(['port_scan','service_scan'])
    def broken(tool,verification=False):
        if tool=='port_scan':raise OSError('controlled network failure')
        return {'status_code':200}
    e.tools.run=broken
    result=e._specialist(a,'Inspect the lab')
    assert result.coverage['complete'] is False
    assert result.coverage['tool_errors'][0]['error']=='controlled network failure'
    assert contexts[1]['coverage_so_far']['tool_errors']==result.coverage['tool_errors']
    assert e.findings==[]


def test_action_budget_does_not_imply_all_tools_tested():
    e,a,gate,contexts,executed=harness(['port_scan'])
    e.llm.config['max_actions_per_specialist']=1
    result=e._specialist(a,'Inspect the lab')
    assert result.coverage['stop_reason']=='action_budget'
    assert result.coverage['untested_tools']==['service_scan']
    assert result.coverage['complete'] is False


@pytest.mark.parametrize('value',[True,0,-1,999,1.5])
def test_invalid_action_budget_fails_before_model_or_execution(value):
    e,a,gate,contexts,executed=harness([])
    e.llm.config['max_actions_per_specialist']=value
    with pytest.raises(ValueError,match='max_actions_per_specialist'):
        e._specialist(a,'Inspect the lab')
    assert contexts==executed==[]


@pytest.mark.parametrize('proof', [{'supported':False}, {'error':'second request timed out'}, None, {'supported':'false'}, {'supported':True,'error':'conflicting observation'}])
def test_failed_independent_reproduction_is_not_a_finding_or_full_coverage(proof):
    e,a,gate,contexts,executed=harness(['xss_test','finish'],role='webapp_agent')
    def execute(tool,*args,**kwargs):
        return {'allowed':True,'result':proof if tool=='verify_xss' else {'supported':True},'audit_entry_id':'audit'}
    a.execute_tool=execute
    result=e._specialist(a,'Inspect the lab')
    assert result.coverage['verification_issues'] and not result.coverage['complete']
    assert e.findings==a.findings==[]


def test_negative_test_result_counts_as_observed_not_as_vulnerability():
    e,a,gate,contexts,executed=harness(['xss_test','finish'],role='webapp_agent')
    a.execute_tool=lambda *args,**kwargs:{'allowed':True,'result':{'supported':False},'audit_entry_id':'audit'}
    result=e._specialist(a,'Inspect the lab')
    assert result.coverage['successful_tools']==['xss_test']
    assert not result.coverage['verification_issues'] and e.findings==[]


@pytest.mark.parametrize('observation', [{'supported':'false'}, {'supported':True,'error':'conflicting observation'}])
def test_malformed_candidate_cannot_trigger_verified_finding(observation):
    e,a,gate,contexts,executed=harness(['xss_test','finish'],role='webapp_agent')
    dispatch=[]
    def execute(tool,*args,**kwargs):
        dispatch.append(tool)
        return {'allowed':True,'result':observation,'audit_entry_id':'audit'}
    a.execute_tool=execute
    result=e._specialist(a,'Inspect the lab')
    assert dispatch==['xss_test'] and e.findings==[]
    assert 'xss_test' not in result.coverage['successful_tools']
    assert result.coverage['tool_errors']
