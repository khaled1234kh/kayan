"""Score the offline Risk Plan and Option A on prelabelled fictional profiles."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from console.backend.planning_api import install_planning_api
from grounding.retrieval import local_index


FIXTURE = Path(__file__).with_name('fixtures') / 'planning_context_validity.json'
REFERENCES = {
    'vendor_remote_access': 'T1133',
    'recovery_readiness': 'T1490',
    'api_object_access': 'A01:2025',
    'web_input_processing': 'A05:2025',
    'cloud_object_access': 'T1530',
    'shared_identity': 'A07:2025',
    'industrial_segmentation': 'T1021',
    'legacy_components': 'A03:2025',
}
UNASSESSED = ('severity', 'impact', 'likelihood', 'mitigation_urgency')


def score_case(client, case, pinned):
    profile = case['engagement_context']
    payload = {'engagement_context': profile}
    phase_one = client.post('/planning/risk-plan', json=payload)
    phase_one.raise_for_status()
    phase_two = client.post('/planning/direct-mitigation', json=payload)
    phase_two.raise_for_status()
    plan, report = phase_one.json(), phase_two.json()
    risks = plan['risks']
    by_scenario = {risk['scenario_id']: risk for risk in risks}
    expected = set(case['expected_scenarios'])
    observed = set(by_scenario)
    observed.update(item['scenario_id'] for item in plan['additional_supported_scenarios'])
    expected_gaps = case.get('expected_gap', {})
    gaps = {scenario: any(e['signal'] == 'stated control gap' for e in risk['context_evidence'])
            or 'explicitly described' in risk['relevance_basis'] for scenario, risk in by_scenario.items()}
    wrong_gaps = {scenario: {'expected': wanted, 'observed': gaps.get(scenario)}
                  for scenario, wanted in expected_gaps.items() if gaps.get(scenario) != wanted}
    integrity = []
    canonical = json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    if not (profile == plan['context'] == report['narrative_context'] == report['risk_plan']['context']
            and sha256(canonical).hexdigest() == plan['context_integrity']['sha256']):
        integrity.append('context_changed')
    if (plan['target_accessed'] or report['target_accessed'] or report['inference_used']
            or report['findings'] or report['summary']['total_findings']):
        integrity.append('offline_boundary')
    if (plan['status'] != ('hypotheses_available' if risks else 'insufficient_context_or_matches')
            or len(risks) > 3 or plan['supported_scenario_count'] != len(observed)
            or report['risk_plan']['risks'] != risks):
        integrity.append('plan_consistency')

    recommendations = report['mitigation_plan']['recommendations']
    if len(recommendations) != len(risks):
        integrity.append('recommendation_count')
    for position, (risk, recommendation) in enumerate(zip(risks, recommendations), 1):
        reference = risk['reference']
        expected_reference = REFERENCES[risk['scenario_id']]
        if (reference['id'] != expected_reference
                or any(reference[key] != pinned[expected_reference][key]
                       for key in ('framework', 'name', 'source_url', 'description'))):
            integrity.append('incorrect_reference')
        if risk['verified'] or risk['relevance_rank'] != position or any(risk[key] != 'not_assessed' for key in UNASSESSED):
            integrity.append('unsupported_risk_claim')
        if (len(risk['context_evidence']) < 2 or not risk['why_relevant'] or not risk['assumptions']
                or any(profile[e['field']][e['start']:e['end']] != e['excerpt']
                       or e['matched_text'] not in e['excerpt'] for e in risk['context_evidence'])):
            integrity.append('broken_evidence_pointer')
        if (recommendation['risk_ids'] != [risk['id']] or recommendation['finding_ids']
                or recommendation['context_evidence'] != risk['context_evidence']
                or recommendation['references'] != [reference]
                or not recommendation['controls'] or not recommendation['validation_steps']):
            integrity.append('unlinked_recommendation')
    return {
        'id': case['id'], 'expected': sorted(expected), 'observed': sorted(observed),
        'true_positives': len(expected & observed), 'false_positives': sorted(observed - expected),
        'false_negatives': sorted(expected - observed), 'gap_mismatches': wrong_gaps,
        'integrity_errors': sorted(set(integrity)),
        'exact': expected == observed and not wrong_gaps and not integrity,
    }


def run(fixture=FIXTURE):
    raw = fixture.read_bytes()
    cases = json.loads(raw)['cases']
    ids = {case['id'] for case in cases}
    if not cases or len(ids) != len(cases):
        raise ValueError('The fixture must contain at least one case with unique IDs')
    pinned = {item['id']: item for item in local_index().entries}
    app = FastAPI()

    def no_live_state():
        raise AssertionError('Offline planning requested live engagement state')

    install_planning_api(app, no_live_state)
    with TestClient(app) as client:
        results = [score_case(client, case, pinned) for case in cases]
    tp = sum(case['true_positives'] for case in results)
    fp = sum(len(case['false_positives']) for case in results)
    fn = sum(len(case['false_negatives']) for case in results)
    negatives = [case for case in results if not case['expected']]
    return {
        'dataset_sha256': sha256(raw).hexdigest(), 'case_count': len(results),
        'exact_cases': sum(case['exact'] for case in results),
        'correct_abstentions': sum(case['exact'] for case in negatives), 'negative_cases': len(negatives),
        'cases_with_gap_mismatches': sum(bool(case['gap_mismatches']) for case in results),
        'cases_with_integrity_errors': sum(bool(case['integrity_errors']) for case in results),
        'true_positives': tp, 'false_positives': fp, 'false_negatives': fn,
        'micro_f1': 2 * tp / (2 * tp + fp + fn) if (tp or fp or fn) else None,
        'cases': results,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--output', type=Path, required=True, help='New JSON file')
    args = parser.parse_args()
    data = run(args.fixture)
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    print(json.dumps({key: value for key, value in data.items() if key != 'cases'}, indent=2))
