"""Recheck saved Go dispatches against recorded signed menus, without execution."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
from urllib.parse import urlsplit


def check(raw_path, output):
    raw_path = Path(raw_path)
    verified = json.loads(raw_path.with_name(raw_path.stem+'_verified.json').read_text())
    raw_bytes = raw_path.read_bytes()
    raw = json.loads(raw_bytes)
    digest = hashlib.sha256(raw_bytes).hexdigest()
    assert digest == verified['source_sha256'], 'Saved raw artifact hash mismatch'
    profiles = {f['flow_id']:f['profile'] for f in raw['flows']}
    dispatches, intents = [], set()
    for entry in raw['audit']:
        args = entry.get('tool_args', {})
        if entry['decision'] != 'ALLOW' or not args.get('_operator_intent_id'):
            continue
        flow = args['_upstream_flow_id']
        profile = profiles[flow]
        proposal = args['_model_proposal']['input']
        assert proposal in profile['approved_commands'], 'Proposal absent from recorded menu'
        assert entry['agent_role'] == profile['role']
        assert args['input'] == proposal.replace('curl -q -s', "curl -q --noproxy '*' -s", 1)
        endpoint = shlex.split(args['input'])[-1]
        assert endpoint in profile['allowed_endpoints']
        assert entry['target'] == urlsplit(endpoint).hostname
        intent = hashlib.sha256((profile['role']+':'+proposal).encode()).hexdigest()
        assert intent == args['_operator_intent_id'] and intent not in intents
        intents.add(intent)
        dispatches.append({'flow_id':flow, 'role':entry['agent_role'],
            'audit_entry_id':entry['entry_id'], 'input':args['input']})
    actual = []
    for flow in raw['flows']:
        for call in flow['toolcalls']['toolcalls']:
            if call['name'] == 'terminal':
                assert call['status'] == 'finished', 'Unexpected terminal status'
                actual.append((flow['flow_id'], json.loads(call['args'])['input']))
    expected = [(d['flow_id'], d['input']) for d in dispatches]
    assert Counter(actual) == Counter(expected), 'Tool dispatches do not match authorized templates'
    assert len(dispatches) == 5
    counts = Counter(e['decision'] for e in raw['audit'])
    denied = Counter(e['tool_name'] for e in raw['audit'] if e['decision'] == 'DENY')
    assert counts == {'ALLOW':16, 'DENY':15}
    assert denied == {'unmapped:terminal':3, 'unmapped:already-dispatched-intent':9,
        'unmapped:subtask_patch':3}
    result = {'checked_at':datetime.now(timezone.utc).isoformat(), 'source':raw_path.name,
        'source_sha256':digest, 'status':'passed', 'actual_terminal_dispatches':len(actual),
        'recorded_menu_mismatches':0, 'go_only_allowed':counts['ALLOW'],
        'go_only_denied':counts['DENY'], 'denials':dict(denied), 'dispatches':dispatches,
        'limit':'Offline audit/toolcall/menu consistency only; not a new engagement, full signature-chain verification, universal false-allow proof, or per-inference Go enforcement.'}
    with Path(output).open('x', encoding='utf-8') as file:
        json.dump(result,file,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k != 'dispatches'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw')
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    check(args.raw,args.output)
