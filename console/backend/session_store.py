"""Atomic engagement snapshots shared by HTTP sessions and the existing WebSocket."""
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path


class SessionStore:
    def __init__(self, directory):
        self.directory = Path(directory)

    def path(self, engagement_id):
        # Arbitrary IDs never become filesystem paths.
        return self.directory / (hashlib.sha256(engagement_id.encode()).hexdigest() + ".json")

    def save(self, state):
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.path(state["engagement_id"])
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        temporary.replace(destination)
        pointer = self.directory / 'current-session.json'
        pending = pointer.with_suffix('.tmp')
        pending.write_text(json.dumps({'engagement_id': state['engagement_id']}), encoding='utf-8')
        pending.replace(pointer)

    def load(self, engagement_id):
        try:
            state = json.loads(self.path(engagement_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if not isinstance(state, dict) or state.get("engagement_id") != engagement_id:
            raise ValueError("Stored engagement ID mismatch")
        return state

    def current(self):
        """Restore records only. A pointer is authoritative; corruption never selects another run."""
        pointer = self.directory / 'current-session.json'
        if pointer.is_file():
            value = json.loads(pointer.read_text(encoding='utf-8'))
            eid = value.get('engagement_id') if isinstance(value, dict) else None
            if not isinstance(eid, str) or not eid:
                raise ValueError('Invalid current-session pointer')
            state = self.load(eid)
            if state is None:
                raise ValueError('Current-session snapshot is missing')
            return state
        # One-time migration for installations predating the pointer. Only hashed
        # session files whose IDs match their filenames qualify, newest first.
        for candidate in sorted(self.directory.glob('*.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True):
            if not re.fullmatch(r'[0-9a-f]{64}\.json', candidate.name):
                continue
            try:
                state = json.loads(candidate.read_text(encoding='utf-8'))
                if (isinstance(state, dict) and isinstance(state.get('engagement_id'), str)
                        and self.path(state['engagement_id']).name == candidate.name
                        and state.get('status') in ('completed', 'failed', 'active', 'starting')):
                    return state
            except (ValueError, OSError):
                continue
        return None


def restored_records(state):
    """Never restart inference, tools, ROE loading or queued instruction delivery."""
    result = deepcopy(state)
    interrupted = result.get('status') in ('active', 'starting')
    result['restoration'] = {'records_only': True, 'interrupted': interrupted,
        'notice': 'Saved session restored. No model, tools or queued instructions were resumed.'}
    if interrupted:
        result['restoration']['original_status'] = result['status']
        result['status'] = 'failed'
        result['runtime_error'] = 'Runtime interrupted by restart. Saved evidence restored; no actions resumed.'
        for agent in result.get('agents', []):
            if agent.get('status') not in ('completed', 'blocked', 'failed'):
                agent.update(status='blocked', current_task=None, activity='Runtime interrupted; no actions resumed')
        for message in result.get('messages', []):
            if message.get('status') == 'queued':
                message.update(status='not_delivered_runtime_stopped', reason='Backend restarted; instruction was not resumed')
    return result
