"""Unit checks use mocked I/O; real local model/socket checks live in eval/."""
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from console.backend import live_api
from console.backend.main import merge_transcript
from integration.bridge_signing import bridge_signature
from pentagi.ollama_client import OllamaClient


@pytest.fixture
def governed(monkeypatch):
    state = {"engagement_id": "unit", "status": "active", "roe": {"targets": ["127.0.0.1"]},
        "agents": [{"agent_id": "recon1", "role": "recon_agent", "status": "working"}]}
    calls = []
    async def authorize(*args):
        calls.append(args)
        denied = args[-1] is True
        return {"decision": "DENY" if denied else "ALLOW", "reason": "unit policy", "audit_entry_id": "unit-audit"}
    monkeypatch.setattr(live_api, "gate_authorize", authorize)
    async def mutate(change):
        return change(state)
    app = FastAPI()
    live_api.install_live_api(app, lambda: state, mutate)
    with TestClient(app) as client:
        yield client, state, calls


def message(**extra):
    return {"engagement_id": "unit", "kind": "instruction", "text": "Keep the lab scope unchanged", "operator_id": "unit-operator", **extra}


def test_instruction_is_queued_until_authenticated_boundary_and_ack_is_idempotent(governed):
    client, state, calls = governed
    response = client.post('/agents/recon1/messages', json=message())
    assert response.status_code == 202
    item = response.json()
    assert state['messages'][0]['status'] == 'queued'
    assert calls[0][5] == 'operator-instruction'
    payload = {'engagement_id': 'unit', 'message_ids': [item['id']]}
    assert client.post('/messages/ack', json=payload).status_code == 403
    assert state['messages'][0]['status'] == 'queued'
    headers = {'X-Kayan-Bridge': bridge_signature(payload)}
    assert client.post('/messages/ack', json=payload, headers=headers).json()['delivered_message_ids'] == [item['id']]
    assert state['messages'][0]['status'] == 'delivered_at_task_boundary'
    assert client.post('/messages/ack', json=payload, headers=headers).json()['delivered_message_ids'] == []
    assert sum(t['kind'] == 'instruction_delivered' for t in state['transcript']) == 1


def test_target_tainted_message_is_denied_before_queue_or_inference(governed):
    client, state, calls = governed
    response = client.post('/agents/recon1/messages', json=message(source='target'))
    assert response.status_code == 403 and calls[0][-1] is True
    assert not state.get('messages')
    assert [e['kind'] for e in state['transcript']] == ['authorization_decision']


def test_agent_bus_requires_signature_and_enrolled_sender(governed):
    client, state, calls = governed
    payload = {'engagement_id':'unit', 'sender_agent_id':'ghost', 'recipient_agent_id':'recon1', 'text':'scan'}
    assert client.post('/messages/route', json=payload).status_code == 403
    assert client.post('/messages/route', json=payload, headers={'X-Kayan-Bridge':bridge_signature(payload)}).status_code == 404
    assert calls == []


def test_completed_agent_cannot_claim_to_accept_new_instruction(governed):
    client, state, calls = governed
    state['agents'][0]['status'] = 'completed'
    assert client.post('/agents/recon1/messages', json=message()).status_code == 409
    assert calls == [] and not state.get('messages')


def test_stream_updates_preserve_operator_entries_and_sequence():
    initial = [{'id':'stream', 'seq':1, 'output':'a'}, {'id':'operator', 'seq':2, 'content':'status?'}]
    result = merge_transcript(initial, [{'id':'stream','output':'abc'}, {'id':'tool','content':'actual'}])
    assert [t['id'] for t in result] == ['stream','operator','tool']
    assert result[0]['output'] == 'abc' and [t['seq'] for t in result] == [1,2,3]


class Reply(BaseModel):
    reply: str


@pytest.mark.parametrize('complete', [True, False])
def test_ollama_requires_completed_stream_and_exposes_explicit_fallback(complete):
    config = {'base_url':'http://unit.local', 'model':'qwen2.5:7b', 'fallback_model':'qwen2.5:1.5b', 'num_ctx':4096, 'num_predict':384}
    def handle(request):
        if request.url.path == '/api/tags':
            return httpx.Response(200,json={'models':[{'name':'qwen2.5:1.5b'}]})
        payload = json.loads(request.content)
        assert payload['model'] == 'qwen2.5:1.5b' and payload['stream'] is True
        assert payload['format']['properties']['reply']['type'] == 'string'
        frames = [{'message':{'content':'{"reply":"actual mock stream"}'}}]
        if complete:
            frames.append({'done':True,'model':'qwen2.5:1.5b','eval_count':7})
        return httpx.Response(200,text='\n'.join(json.dumps(f) for f in frames))
    client = OllamaClient(config, httpx.MockTransport(handle))
    try:
        assert 'explicit compute fallback' in client.selection_reason
        if complete:
            updates = []
            result = client.chat([], Reply, updates.append)
            assert result['parsed'].reply == 'actual mock stream' and updates[-1] == result['text']
        else:
            with pytest.raises(RuntimeError, match='without a completed response'):
                client.chat([], Reply)
    finally:
        client.close()
