"""Restart restores evidence, never a runtime or its authority."""
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from console.backend import main
from console.backend.session_store import SessionStore, restored_records


def completed(eid='saved'):
    return {'engagement_id':eid,'status':'completed','execution_engine':'local_llm',
            'agents':[{'agent_id':'planner1','role':'planner_agent','status':'completed'}],
            'findings':[{'id':'verified-original'}],
            'transcript':[{'id':'original','timestamp':1,'agent_id':'planner1',
                          'agent_role':'planner_agent','kind':'agent_completed','content':'Saved original record','seq':1}]}


def test_pointer_is_authoritative_over_newer_unselected_snapshots(tmp_path):
    store=SessionStore(tmp_path);store.save(completed())
    store.path('other').write_text(json.dumps(completed('other')),encoding='utf-8')
    assert store.current()['engagement_id']=='saved'


def test_legacy_migration_ignores_unhashed_or_id_mismatched_files(tmp_path):
    store=SessionStore(tmp_path)
    store.path('saved').write_text(json.dumps(completed()),encoding='utf-8')
    (tmp_path/'random.json').write_text(json.dumps(completed('wrong')),encoding='utf-8')
    store.path('foreign').write_text(json.dumps(completed('wrong')),encoding='utf-8')
    assert store.current()['engagement_id']=='saved'


@pytest.mark.parametrize('pointer', ['broken JSON', '{"engagement_id":"missing"}', '{}'])
def test_corrupt_pointer_does_not_silently_fall_back(tmp_path,pointer):
    store=SessionStore(tmp_path);store.save(completed())
    (tmp_path/'current-session.json').write_text(pointer,encoding='utf-8')
    with pytest.raises(ValueError):store.current()


def test_interrupted_runtime_is_not_resumed_and_original_evidence_is_preserved():
    state=completed();state.update(status='active',messages=[{'id':'instruction','status':'queued'}])
    state['agents'][0].update(status='working',current_task='Old task')
    original=deepcopy(state);restored=restored_records(state)
    assert state==original
    assert restored['status']=='failed' and restored['agents'][0]['status']=='blocked'
    assert restored['agents'][0]['current_task'] is None
    assert restored['messages'][0]['status']=='not_delivered_runtime_stopped'
    assert restored['findings']==state['findings'] and restored['transcript']==state['transcript']
    assert restored['restoration']['records_only'] and restored['restoration']['interrupted']


def test_backend_startup_restores_same_snapshot_without_any_inference_or_authorization(tmp_path,monkeypatch):
    store=SessionStore(tmp_path);state=completed();store.save(state)
    monkeypatch.setattr(main,'session_store',store)
    monkeypatch.setattr(main,'_engagement_state',{})
    monkeypatch.setattr(main,'_revision',0)
    from console.backend import live_api
    async def forbidden(*args,**kwargs):raise AssertionError('Restoration must not authorize any action')
    monkeypatch.setattr(live_api,'gate_authorize',forbidden)
    with TestClient(main.app) as client:
        result=client.get('/engagement').json()
        assert result['engagement_id']=='saved' and result['status']=='completed'
        assert result['transcript']==state['transcript'] and result['findings']==state['findings']
        assert result['restoration']['records_only']
        with client.websocket_connect('/ws') as socket:
            assert socket.receive_json()['data']['restoration']==result['restoration']


def test_backend_startup_corruption_is_visible_without_fabricating_an_engagement(tmp_path,monkeypatch):
    store=SessionStore(tmp_path);tmp_path.joinpath('current-session.json').write_text('{}')
    monkeypatch.setattr(main,'session_store',store);monkeypatch.setattr(main,'_engagement_state',{})
    with TestClient(main.app) as client:
        state=client.get('/engagement').json()
        assert state['status']=='waiting' and 'engagement_id' not in state
        assert 'could not be restored' in state['restoration']['notice']


def test_non_object_snapshot_fails_visibly_instead_of_crashing_startup(tmp_path,monkeypatch):
    store=SessionStore(tmp_path);store.save(completed());store.path('saved').write_text('[]')
    monkeypatch.setattr(main,'session_store',store);monkeypatch.setattr(main,'_engagement_state',{})
    with TestClient(main.app) as client:
        result=client.get('/engagement').json()
        assert result['status']=='waiting' and 'could not be restored' in result['restoration']['notice']
