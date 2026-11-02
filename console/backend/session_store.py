"""Atomic engagement snapshots shared by HTTP sessions and the existing WebSocket."""
import hashlib
import json
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

    def load(self, engagement_id):
        try:
            state = json.loads(self.path(engagement_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if state.get("engagement_id") != engagement_id:
            raise ValueError("Stored engagement ID mismatch")
        return state
