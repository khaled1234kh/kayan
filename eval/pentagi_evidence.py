"""Verify raw Go terminal evidence with a separately gated, fresh lab nonce."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from eval.pentagi_runtime_check import audit_rows
from integration.trustgate_client import TrustGateClient
from pentagi.lab_tools import LabTools
from eval.scope_violation_tests.run_eval import assess_finding_evidence


def candidates(raw):
    found = []
    for flow in raw['flows']:
        evidence = flow['profile']['expected_evidence']
        for kind, expected in evidence.items():
            for call in flow.get('toolcalls',{}).get('toolcalls',[]):
                if call['name'] != 'terminal' or call['status'] != 'finished':
                    continue
                args = json.loads(call['args']) if isinstance(call['args'], str) else call['args']
                action = {'xss':'xss_test','command_injection':'command_injection_test','path_traversal':'directory_traversal'}[kind]
                authorized = any(row['decision'] == 'ALLOW' and row['tool_name'] == action
                    and row.get('tool_args',{}).get('_upstream_flow_id') == flow['flow_id']
                    and row['tool_args'].get('input') == args.get('input') for row in raw.get('audit',[]))
                if not authorized:
                    continue
                output = call.get('result','')
                if output.startswith('terminal tool '):
                    continue  # Upstream can record a swallowed terminal error as finished.
                supported = expected.get('payload','MISSING_PAYLOAD') in output if kind == 'xss' else (
                    bool(re.search(r'(?m)^'+re.escape(expected['marker'])+r'\s*$',output.replace('</pre>','\n')))
                    if kind == 'command_injection' else expected['marker'] in output)
                if supported:
                    found.append({'type':kind,'flow_id':flow['flow_id'],'toolcall_id':call['id'],
                        'marker':expected['marker'],'observed_response':output})
                    break
    return found


def verify(path):
    source = Path(path)
    raw = json.loads(source.read_text(encoding='utf-8'))
    output = source.with_name(source.stem+'_verified.json')
    if output.exists():
        raise FileExistsError('Preserve the existing verification artifact')
    result = {'checked_at':datetime.now(timezone.utc).isoformat(),'source':source.name,
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'engagement_id':raw['engagement_id'],'candidates':candidates(raw),'findings':[],
        'accuracy_limit':'Independent fresh-nonce reproduction, not blinded classification accuracy; XSS is raw reflection, not browser execution'}
    with output.open('x',encoding='utf-8') as file:
        json.dump(result,file)
    client,tools = TrustGateClient(),LabTools('http://127.0.0.1:8888')
    actions = {'xss':'xss_test','command_injection':'command_injection_test','path_traversal':'directory_traversal'}
    mitre = {'xss':'T1190','command_injection':'T1059','path_traversal':'T1190'}
    try:
        for candidate in result['candidates']:
            action = actions[candidate['type']]
            decision = client.authorize(raw['engagement_id'],'go-comparison-verifier','webapp_agent',
                action,{'purpose':'independent fresh-nonce reproduction of raw Go evidence','source_flow':candidate['flow_id'],
                    'source_toolcall':candidate['toolcall_id']},'127.0.0.1','web-app',{'target':'trusted'})
            candidate['verification_gate'] = {'decision':decision.decision,'reason':decision.reason,'audit_entry_id':decision.audit_entry_id}
            if not decision.allowed:
                continue
            reproduced = candidate['verification'] = tools.run(action,verification=True)
            if reproduced['supported'] and reproduced['marker'] != candidate['marker']:
                result['findings'].append({**candidate,'mitre_technique':mitre[candidate['type']],'verified':True})
    finally:
        rows = audit_rows(raw['engagement_id'])
        counts = Counter(row['decision'] for row in rows)
        go_only = [row for row in rows if row['agent_id'] != 'go-comparison-verifier']
        result.update(finding_count=len(result['findings']),allowed=counts['ALLOW'],denied=counts['DENY'],
            go_only_allowed=sum(row['decision']=='ALLOW' for row in go_only),
            go_only_denied=sum(row['decision']=='DENY' for row in go_only),
            mitre_coverage_percent=100*len(set(f['mitre_technique'] for f in result['findings']))/5,
            reproduction_percent=100*len(result['findings'])/len(result['candidates']) if result['candidates'] else None,
            counts_basis='All Go flow-start/workflow/executor gate records plus independent reproduction authorizations, excluding ROE load and rejected HTTP headers; not the Python per-model-call denominator',audit=rows)
        result['legacy_evidence_precision'] = assess_finding_evidence([
            {'id':str(item['flow_id'])+':'+str(item['toolcall_id']), 'type':item['type'],
             'evidence':item['verification']} for item in result['findings']])
        output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
        client.close()
        tools.close()
    print(json.dumps({k:v for k,v in result.items() if k in ('finding_count','allowed','denied','go_only_allowed','go_only_denied','mitre_coverage_percent','reproduction_percent')}))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact')
    verify(parser.parse_args().artifact)
