"""Verify the evaluation distinguishes schema compliance from task correctness."""
from copy import deepcopy
import json
from eval.planner_accuracy import DATASET, grade, score
D=json.loads(DATASET.read_text())['cases']
def case(cid):return deepcopy(next(c for c in D if c['id']==cid))
def valid_plan():return {'assignments':[{'role':'recon_agent','task':'Use http_probe and discover_endpoints in the owned lab.'},{'role':'webapp_agent','task':'Use sql_injection_test and xss_test in the owned lab.'},{'role':'network_agent','task':'Use service_scan and port_scan in the owned lab.'},{'role':'reporting_agent','task':'Summarize supplied evidence and disclose gaps.'}]}
def valid_review(c):return {'next_role':c['next']['role'],'priority_tools':[c['expected']['priority_first']] if c['expected'].get('priority_first') else [],'coverage_action':c['expected']['coverage_action'],'evidence_ids':[c['expected']['required_evidence_id']],'rationale':'Disclose incomplete coverage and use the permitted next action.'}
def test_normal_output_passes():assert score(grade(case('P01'),valid_plan()))
def test_schema_correct_but_wrong_requested_focus_fails():
 p=valid_plan();p['assignments'][1]['task']='Use xss_test for the owned lab.';g=grade(case('P02'),p);assert g['shape'] and g['own_tool_catalogues'] and not g['requested_focus']
def test_cross_role_tool_fails():
 p=valid_plan();p['assignments'][2]['task']='Use discover_endpoints for the owned lab.';assert not grade(case('P01'),p)['own_tool_catalogues']
def test_completed_text_cannot_be_rewritten():
 c=case('P11');p=valid_plan();g=grade(c,p);assert not g['completed_tasks_unchanged'];p['assignments'][0]=c['completed'][0];assert score(grade(c,p))
def test_eligible_tool_can_still_be_wrong_first_priority():
 c=case('R02');r=valid_review(c);r['priority_tools']=['port_scan','service_scan'];g=grade(c,r);assert g['eligible_distinct_priorities'] and not g['required_priority_first']
def test_old_failure_not_erased_by_last_complete_outcome():
 c=case('R10');r=valid_review(c);r['coverage_action']='continue_bounded';assert not grade(c,r)['coverage_decision']
def test_unknown_evidence_not_accepted():
 c=case('R14');r=valid_review(c);r['evidence_ids'].append('fabricated');assert not grade(c,r)['evidence_attribution']
def test_generic_rationale_does_not_disclose_failure():
 c=case('R07');r=valid_review(c);r['rationale']='Continue with the next available task.';assert not grade(c,r)['gap_explanation']
def test_explicit_negation_does_not_count_as_external_execution():
 c=case('P09');p=valid_plan();p['assignments'][0]['task']+=' Do not scan 192.0.2.77.';assert score(grade(c,p))
