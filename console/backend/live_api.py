"""Governed operator input and the live runtime on the existing console state/socket."""
import asyncio
import hmac
import time
import uuid
from typing import Literal

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from integration.bridge_signing import bridge_signature
from pentagi.ollama_client import OllamaClient
from pentagi.engagement_context import EngagementContext

ROLE_TECHNIQUE = {"planner_agent": "planning", "recon_agent": "recon", "webapp_agent": "web-app", "network_agent": "network", "reporting_agent": "reporting"}


class OperatorMessage(BaseModel):
    engagement_id: str
    kind: Literal["status", "instruction"]
    text: str = Field(min_length=1, max_length=2000)
    operator_id: str = Field(min_length=1, max_length=100)
    source: Literal["operator", "target"] = "operator"


class RoutedMessage(BaseModel):
    engagement_id: str
    sender_agent_id: str
    recipient_agent_id: str
    text: str = Field(min_length=1, max_length=2000)


class Acknowledge(BaseModel):
    engagement_id: str
    message_ids: list[str]


class StartRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operator_id: str = Field(min_length=1, max_length=100)
    authorization: Literal["I_AUTHORIZE_OWNED_LAB"]
    grounding_enabled: bool = True
    engagement_context: EngagementContext | None = None


class StatusReply(BaseModel):
    reply: str = Field(max_length=1800)


async def gate_authorize(state, role, agent_id, tool, args, technique, untrusted=False):
    targets = state.get("roe", {}).get("targets", [])
    if not targets:
        raise HTTPException(409, "No signed ROE scope is loaded")
    payload = {"engagement_id": state["engagement_id"], "agent_id": agent_id, "agent_role": role,
        "tool_name": tool, "tool_args": args, "target": targets[0], "technique": technique,
        "provenance": {"target": "trusted", "body": "untrusted" if untrusted else "trusted"}}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post("http://127.0.0.1:8000/authorize", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as error:
        raise HTTPException(503, f"TrustGate unavailable; message not delivered: {error}") from error


def install_live_api(app, get_state, mutate):
    active_job = None
    running_status_jobs = set()
    start_lock = asyncio.Lock()

    async def mutate_for(eid, transform):
        def checked(state):
            if state.get("engagement_id") != eid:
                raise HTTPException(409, "Engagement changed before delivery")
            return transform(state)
        return await mutate(checked)

    def current(eid, agent_id=None):
        state = get_state()
        if state.get("engagement_id") != eid:
            raise HTTPException(409, "Message requires the current engagement")
        if agent_id is None:
            return state
        agent = next((a for a in state.get("agents", []) if agent_id in (a.get("agent_id"), a.get("role"))), None)
        if agent is None:
            raise HTTPException(404, "Agent is not enrolled in this engagement")
        return agent

    async def record(eid, agent, kind, content, **details):
        entry = {"id": uuid.uuid4().hex, "timestamp": int(time.time()*1000), "engagement_id": eid,
                 "agent_id": agent["agent_id"], "agent_role": agent["role"], "model_tier": agent.get("model_tier"),
                 "kind": kind, "type": "llm_call" if kind.startswith("llm_") else "status_change",
                 "content": content, **details}
        def append(state):
            if state.get("engagement_id") != eid:
                raise HTTPException(409, "Engagement changed before delivery")
            entries = state.setdefault("transcript", [])
            entry["seq"] = len(entries)+1
            entries.append(entry)
            return entry
        return await mutate(append)

    async def authorize(eid, agent, role, sender_id, tool, args, technique, untrusted=False):
        decision = await gate_authorize(current(eid), role, sender_id, tool, args, technique, untrusted)
        await record(eid, agent, "authorization_decision", f"{decision['decision']}: {tool} — {decision['reason']}",
                     tool_name=tool, decision=decision["decision"], reason=decision["reason"],
                     audit_entry_id=decision.get("audit_entry_id"), target=current(eid)["roe"]["targets"][0])
        if decision["decision"] != "ALLOW":
            raise HTTPException(403, {"reason": decision["reason"], "audit_entry_id": decision.get("audit_entry_id")})
        return decision

    async def answer_status(eid, agent, message):
        client = None
        entry = None
        try:
            await authorize(eid, agent, agent["role"], agent["agent_id"], "llm_inference", {"purpose": "operator status"}, ROLE_TECHNIQUE[agent["role"]])
            client = await asyncio.to_thread(OllamaClient)
            entry = await record(eid, agent, "llm_call_started", "Answering a governed operator status question", model_name=client.model, output="", streaming=True)
            loop = asyncio.get_running_loop()
            def delta(output):
                async def update():
                    def change(state):
                        for item in state.get("transcript", []):
                            if item["id"] == entry["id"]:
                                item["output"] = output
                    await mutate_for(eid, change)
                asyncio.run_coroutine_threadsafe(update(), loop).result(timeout=10)
            state = current(eid)
            facts = {"agent": agent, "engagement_status": state.get("status"),
                     "verified_findings": [f for f in state.get("findings", []) if f.get("verified") and f.get("agent") == agent["role"]]}
            result = await asyncio.to_thread(client.chat, [
                {"role": "system", "content": "Answer the operator status question using only the supplied recorded facts. Do not invent actions or findings. You cannot change tasks or execute tools. Return JSON with reply."},
                {"role": "user", "content": __import__('json').dumps({"question": message["text"], "facts": facts})},
            ], StatusReply, delta)
            await authorize(eid, agent, agent["role"], agent["agent_id"], "message_send", {"recipient": "operator", "body": result["parsed"].reply}, "agent-message")
            await record(eid, agent, "operator_reply", result["parsed"].reply, model_name=result["model"], message_id=message["id"])
            def finish(state):
                for item in state.get("transcript", []):
                    if item["id"] == entry["id"]:
                        item.update(streaming=False, output=result["text"], elapsed_seconds=result["elapsed_seconds"])
                for item in state.get("messages", []):
                    if item["id"] == message["id"]:
                        item["status"] = "answered"
            await mutate_for(eid, finish)
        except Exception as error:
            if get_state().get("engagement_id") == eid:
                await record(eid, agent, "operator_reply_error", f"Status response failed: {error}", message_id=message["id"])
                def failed(state):
                    for item in state.get("transcript", []):
                        if entry and item["id"] == entry["id"]:
                            item.update(streaming=False, error=str(error))
                    for item in state.get("messages", []):
                        if item["id"] == message["id"]:
                            item["status"] = "failed"
                await mutate_for(eid, failed)
        finally:
            if client:
                client.close()

    @app.post("/agents/{agent_id}/messages", status_code=202)
    async def operator_message(agent_id: str, message: OperatorMessage):
        agent = current(message.engagement_id, agent_id)
        state = current(message.engagement_id)
        if message.kind == "instruction" and state.get("status") not in ("active", "ready"):
            raise HTTPException(409, "Instructions require a live or ready engagement")
        if message.kind == "instruction" and agent.get("status") == "completed":
            raise HTTPException(409, "This agent has no remaining task boundary")
        decision = await authorize(message.engagement_id, agent, "operator", message.operator_id, "message_send",
            {"recipient": agent["agent_id"], "body": message.text}, "operator-"+message.kind, message.source == "target")
        item = {"id": uuid.uuid4().hex, "agent_id": agent["agent_id"], "kind": message.kind,
                "text": message.text, "operator_id": message.operator_id,
                "status": "queued" if message.kind == "instruction" else "answering", "audit_entry_id": decision["audit_entry_id"]}
        await mutate_for(message.engagement_id, lambda state: state.setdefault("messages", []).append(item))
        await record(message.engagement_id, agent, "operator_message", message.text, message_id=item["id"], delivery_status=item["status"])
        if message.kind == "status":
            task = asyncio.create_task(answer_status(message.engagement_id, agent, item))
            running_status_jobs.add(task)
            task.add_done_callback(running_status_jobs.discard)
        return item

    @app.get("/agents/{agent_id}/messages/pending")
    async def pending(agent_id: str, engagement_id: str):
        agent = current(engagement_id, agent_id)
        return {"messages": [m for m in current(engagement_id).get("messages", []) if m["agent_id"] == agent["agent_id"] and m["kind"] == "instruction" and m["status"] == "queued"]}

    def check_bridge(request, payload):
        signature = request.headers.get("X-Kayan-Bridge", "")
        if not hmac.compare_digest(signature, bridge_signature(payload)):
            raise HTTPException(403, "Internal agent bridge authentication failed")

    @app.post("/messages/ack")
    async def acknowledge(payload: Acknowledge, request: Request):
        check_bridge(request, payload.model_dump())
        state = current(payload.engagement_id)
        delivered = []
        def mark(state):
            for message in state.get("messages", []):
                if message["id"] in payload.message_ids and message["kind"] == "instruction" and message["status"] == "queued":
                    message["status"] = "delivered_at_task_boundary"
                    delivered.append(message["id"])
        await mutate_for(payload.engagement_id, mark)
        for message in state.get("messages", []):
            if message["id"] in delivered:
                agent = current(payload.engagement_id, message["agent_id"])
                await record(payload.engagement_id, agent, "instruction_delivered",
                    "Queued instruction delivered at a safe task boundary", message_id=message["id"])
        return {"status": "ok", "delivered_message_ids": delivered}

    @app.post("/messages/route")
    async def route(payload: RoutedMessage, request: Request):
        check_bridge(request, payload.model_dump())
        sender = current(payload.engagement_id, payload.sender_agent_id)
        recipient = current(payload.engagement_id, payload.recipient_agent_id)
        decision = await authorize(payload.engagement_id, recipient, sender["role"], sender["agent_id"], "message_send",
            {"recipient": recipient["agent_id"], "body": payload.text}, "agent-message")
        entry = await record(payload.engagement_id, recipient, "agent_message", payload.text,
            sender_agent_id=sender["agent_id"], recipient_agent_id=recipient["agent_id"], audit_entry_id=decision["audit_entry_id"])
        return {"delivered": True, "id": entry["id"], "audit_entry_id": decision["audit_entry_id"]}

    @app.post("/engagement/start", status_code=202)
    async def start(payload: StartRequest):
        async with start_lock:
            nonlocal active_job
            if (active_job is not None and not active_job.done()) or any(not job.done() for job in running_status_jobs):
                raise HTTPException(409, "A live assessment is already running")
            eid = str(uuid.uuid4())
            def initialize(state):
                state.clear()
                state.update(engagement_id=eid, status="starting", execution_engine="local_llm", transcript=[], agents=[], findings=[], messages=[])
            await mutate(initialize)
            async def job():
                def run():
                    from pentagi.live_engagement import LiveEngagement
                    engagement = None
                    try:
                        engagement = LiveEngagement(grounding_enabled=payload.grounding_enabled)
                        engagement.create_engagement(payload.operator_id, engagement_id=eid,
                            engagement_context=payload.engagement_context)
                        engagement.run()
                    finally:
                        if engagement:
                            engagement.close()
                try:
                    await asyncio.to_thread(run)
                except Exception as error:
                    def fail(state):
                        if state.get("engagement_id") == eid:
                            state.update(status="failed", runtime_error=str(error))
                    await mutate(fail)
            active_job = asyncio.create_task(job())
            return {"engagement_id": eid, "status": "starting"}
