"""Operations console backend — FastAPI.

Reads TrustGate audit log and engagement state, pushes updates over WebSocket.
"""

import json
import asyncio
import uuid
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from console.backend.session_store import SessionStore

app = FastAPI(title="KAYAN TrustGate Console", version="0.1.0")

ALLOWED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:5174", "http://localhost:5174"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def check_browser_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin is not None and origin not in ALLOWED_ORIGINS:
        return JSONResponse({"detail": "Browser origin is not allowed"}, status_code=403)
    return await call_next(request)

# Connected WebSocket clients
_clients: List[WebSocket] = []

# Engagement state (updated by orchestrator)
_engagement_state: Dict[str, Any] = {}
_session_id = uuid.uuid4().hex
_revision = 0
_state_lock = asyncio.Lock()
session_store = SessionStore(Path(__file__).resolve().parents[2] / "data/engagement_sessions")


class TranscriptEntry(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1)
    timestamp: int
    agent_id: str
    agent_role: str
    kind: str
    content: str


class EngagementUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")
    engagement_id: str = Field(min_length=1)
    agents: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    denials: List[Dict[str, Any]] = Field(default_factory=list)
    transcript: List[TranscriptEntry] = Field(default_factory=list)


def snapshot():
    return {**(_engagement_state or {"status": "waiting"}),
            "protocol_version": 1, "session_id": _session_id, "revision": _revision}


def merge_transcript(old_entries, incoming):
    merged = {entry["id"]: dict(entry) for entry in old_entries}
    for entry in incoming:
        old = merged.get(entry["id"])
        merged[entry["id"]] = {**entry, "seq": old["seq"] if old else len(merged) + 1}
    return list(merged.values())


async def mutate_state(transform):
    global _revision
    async with _state_lock:
        result = transform(_engagement_state)
        if _engagement_state.get("engagement_id"):
            session_store.save(_engagement_state)
        _revision += 1
        await broadcast({"type": "engagement_update", "data": snapshot()})
        return result


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if websocket.headers.get("origin") not in (None, *ALLOWED_ORIGINS):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        # Serialize subscription with updates: snapshot always precedes newer frames.
        async with _state_lock:
            _clients.append(websocket)
            await websocket.send_json({"type": "engagement_update", "data": snapshot()})
        while True:
            # Viewers subscribe only. Authoritative updates arrive through HTTP.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _clients:
            _clients.remove(websocket)


async def broadcast(message: dict):
    """Broadcast a message to all connected clients."""
    for client in list(_clients):
        try:
            await client.send_text(json.dumps(message))
        except Exception:
            if client in _clients:
                _clients.remove(client)


@app.post("/engagement/update")
async def update_engagement(update: EngagementUpdate):
    """Receive engagement state updates from the orchestrator."""
    global _revision
    data = update.model_dump(exclude_unset=True)
    async with _state_lock:
        if data["engagement_id"] != _engagement_state.get("engagement_id"):
            _engagement_state.clear()
        data["transcript"] = merge_transcript(_engagement_state.get("transcript", []), data.get("transcript", []))
        _engagement_state.update(data)
        completed = {a["agent_id"] for a in data.get("agents", []) if a.get("status") == "completed"}
        for message in _engagement_state.get("messages", []):
            if message.get("status") == "queued" and message.get("agent_id") in completed:
                message.update(status="not_delivered_agent_completed", reason="No further safe task boundary")
        # Persist the same state consumed by both renderers, never a second state engine.
        session_store.save(_engagement_state)
        _revision += 1
        await broadcast({"type": "engagement_update", "data": snapshot()})
    return {"status": "ok", "revision": _revision}


@app.get("/engagement")
async def get_engagement():
    """Return current engagement state."""
    return snapshot()


@app.get("/agents/{agent_id}/session")
async def get_agent_session(agent_id: str, engagement_id: str):
    state = _engagement_state if engagement_id == _engagement_state.get("engagement_id") else session_store.load(engagement_id)
    if not state:
        raise HTTPException(404, "Engagement not found")
    agent = next((a for a in state.get("agents", []) if agent_id in (a.get("agent_id"), a.get("role"))), None)
    if not agent:
        raise HTTPException(404, "Agent not found in engagement")
    transcript = sorted((t for t in state.get("transcript", []) if t.get("agent_id") == agent["agent_id"]),
                        key=lambda t: (t.get("seq", 0), t["timestamp"]))
    return {**agent, "engagement_id": engagement_id, "transcript": transcript,
            "findings_scope": "coordinated_assessment" if agent["role"] == "planner_agent" else "agent",
            "findings": [f for f in state.get("findings", []) if agent["role"] == "planner_agent" or f.get("agent") == agent["role"]]}


@app.get("/health")
async def health():
    return {"status": "ok", "connected_clients": len(_clients)}


@app.get("/audit")
async def get_audit(limit: int = 100):
    """Proxy to TrustGate audit endpoint."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://127.0.0.1:8000/audit", params={"limit": limit})
        return resp.json()
    except Exception as e:
        return {"error": str(e), "entries": []}


@app.get("/audit/verify")
async def verify_audit():
    """Proxy to TrustGate audit verify endpoint."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://127.0.0.1:8000/audit/verify")
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


from console.backend.live_api import install_live_api
install_live_api(app, lambda: _engagement_state, mutate_state)
from console.backend.planning_api import install_planning_api
install_planning_api(app, lambda: dict(_engagement_state))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


@app.get('/runtime/health')
async def runtime_health():
    """Read-only gate readiness; console connectivity never implies authority."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response=await client.get('http://127.0.0.1:8000/health')
            response.raise_for_status()
            data=response.json()
        available=(isinstance(data,dict) and data.get('status')=='ok' and str(data.get('engine','')).startswith('cedar-policy')
                   and data.get('roe_authentication')=='HMAC-SHA256')
        return {'gate':{'available':available},'live_execution_authorized':False}
    except (httpx.HTTPError, ValueError):
        return {'gate':{'available':False},'live_execution_authorized':False}
