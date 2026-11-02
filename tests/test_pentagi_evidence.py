"""Prevent terminal echoes/errors or ungated database rows becoming findings."""
import json

from eval.pentagi_evidence import candidates


def raw_fixture(output, audit=True):
    return {'flows':[{'flow_id':1,'profile':{'expected_evidence':{
        'command_injection':{'marker':'KAYAN_nonce'}}},'toolcalls':{'toolcalls':[
            {'id':2,'name':'terminal','status':'finished','args':json.dumps({'input':'signed command'}),'result':output}]}}],
        'audit':[{'decision':'ALLOW','tool_name':'command_injection_test',
            'tool_args':{'_upstream_flow_id':1,'input':'signed command'}}] if audit else []}


def test_nonce_in_echoed_command_or_error_does_not_prove_execution():
    assert not candidates(raw_fixture("curl 'http://lab/ping?host=echo+KAYAN_nonce'"))
    assert not candidates(raw_fixture('terminal tool failed: KAYAN_nonce'))


def test_raw_response_requires_corresponding_gate_allow_and_exact_execution_args():
    assert not candidates(raw_fixture('<pre>\nKAYAN_nonce\n</pre>',audit=False))
    raw = raw_fixture('<pre>\nKAYAN_nonce\n</pre>')
    raw['audit'][0]['tool_args']['input'] = 'different command'
    assert not candidates(raw)


def test_standalone_output_with_matching_audit_is_candidate_not_automatic_finding():
    found = candidates(raw_fixture('<pre>\nKAYAN_nonce\n</pre>'))
    assert len(found) == 1 and found[0]['toolcall_id'] == 2
    assert 'verified' not in found[0]
