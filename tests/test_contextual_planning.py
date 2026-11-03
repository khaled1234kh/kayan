"""Deterministic Phase 1/Option A checks, not Qwen Planner accuracy tests."""
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pentagi.engagement_context import descriptive_context
from pentagi.risk_plan import build_risk_plan
from pentagi.agents.reporting_agent import ReportingAgent

CASES=json.loads((Path(__file__).parents[1]/'eval/fixtures/planning_contexts_v2.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case',CASES,ids=lambda case:case['id'])
def test_fictional_context_is_preserved_and_every_hypothesis_has_exact_evidence(case):
    context=case['engagement_context']
    plan=build_risk_plan(context)
    report=ReportingAgent('fictional').generate_direct_mitigation(plan)
    assert plan['context']==report['narrative_context']==report['risk_plan']['context']==context
    raw=json.dumps(context,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    assert plan['context_integrity']['sha256']==hashlib.sha256(raw).hexdigest()
    assert not report['target_accessed'] and not report['findings']
    for risk in plan['risks']:
        assert risk['why_relevant'] and risk['assumptions'] and risk['context_evidence']
        assert 'priority' not in risk and risk['relevance_rank']>=1
        for key in ('severity','impact','likelihood','mitigation_urgency'):assert risk[key]=='not_assessed'
        for evidence in risk['context_evidence']:
            assert context[evidence['field']][evidence['start']:evidence['end']]==evidence['excerpt']
            assert evidence['matched_text'] in evidence['excerpt']
    recommendations=report['mitigation_plan']['recommendations']
    assert len({r['action'] for r in recommendations})==len(recommendations)
    assert all(r['context_evidence'] and r['controls'] and r['validation_steps'] for r in recommendations)


def test_negative_or_non_technical_context_is_not_filled_with_weak_matches():
    for case in CASES[-2:]:
        plan=build_risk_plan(case['engagement_context'])
        assert plan['risks']==[] and plan['status']=='insufficient_context_or_matches'
        assert plan['limitations'] and plan['target_accessed'] is False


def test_recommendations_change_with_organization_and_do_not_invent_crm_or_chat_secrets():
    plans=[build_risk_plan(case['engagement_context']) for case in CASES[:3]]
    scenarios=[{r['scenario_id'] for r in plan['risks']} for plan in plans]
    assert 'vendor_remote_access' in scenarios[0] and 'recovery_readiness' in scenarios[0]
    assert 'shared_identity' in scenarios[1] and not any('web_input' in s for s in scenarios[1])
    assert 'industrial_segmentation' in scenarios[2] and 'legacy_components' in scenarios[2]
    assert len({tuple(sorted(s)) for s in scenarios})==3
    for plan in plans:
        assert not {'T1213.004','T1552.008'} & {r['reference']['id'] for r in plan['risks']}
    reports=[ReportingAgent('fixture').generate_direct_mitigation(p) for p in plans]
    assert len({json.dumps(r['mitigation_plan']['recommendations'],sort_keys=True) for r in reports})==3


def test_long_unicode_multiline_text_is_not_silently_trimmed_or_truncated():
    text='  Fictional business — عميل\n'+('Database design description. '*100)+'  '
    context={'infrastructure_summary':text,'company_size':'A fictional company with '+('multiple sites and teams. '*12)}
    assert descriptive_context(context)==context
    plan=build_risk_plan(context)
    assert plan['context']==context
    with pytest.raises(ValidationError):build_risk_plan({'data_storage':'x'*12001})


def test_saved_verified_findings_get_distinct_controls_without_changing_evidence():
    types=['sql_injection','command_injection','xss','path_traversal']
    findings=[{'id':kind,'type':kind,'target':'http://fictional.invalid',
               'mitre':'T1190','verified':True,
               'verification':{'result':{'supported':True},'audit_entry_id':'audit-'+kind}}
              for kind in types]
    original=json.dumps(findings,sort_keys=True)
    recommendations=ReportingAgent('fixture')._mitigation_plan(findings=findings)['recommendations']
    assert len({r['title'] for r in recommendations})==4
    assert len({r['action'] for r in recommendations})==4
    by_type={r['finding_ids'][0]:r for r in recommendations}
    assert 'parameterized' in by_type['sql_injection']['action'].lower()
    assert 'shell' in by_type['command_injection']['action'].lower()
    assert 'encoding' in by_type['xss']['action'].lower()
    assert 'canonical' in by_type['path_traversal']['action'].lower()
    assert json.dumps(findings,sort_keys=True)==original
    assert ReportingAgent('fixture')._mitigation_plan(findings=[{'id':'unproven','type':'xss','verified':True}])['recommendations']==[]
