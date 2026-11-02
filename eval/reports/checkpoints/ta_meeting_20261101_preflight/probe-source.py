"""Observe a real deterministic fixture; pause before publication to arm the browser.

No synthetic event or console state is inserted. Not an LLM evaluation or final demo.
"""
from pathlib import Path
import json
import sys
import time

ROOT = Path(r"C:\Users\khale\Downloads\kayan-trustgate")
sys.path.insert(0, str(ROOT))
from pentagi.orchestrator import EngagementOrchestrator

OUT = ROOT / "eval/reports/checkpoints/ta_meeting_20261101_preflight"
orchestrator = EngagementOrchestrator(grounding_enabled=True)
observations = []
try:
    eid = orchestrator.create_engagement(
        "pre-meeting-ui-timing", ["127.0.0.1"], ["recon", "web-app", "network"], []
    )
    agent = next(a for a in orchestrator.agents if a.role == "webapp_agent")
    publish = agent.event_sink

    def observe(real_agent, kind, task_id, content, details):
        measured = details.get("tool_name") == "sql_injection_test" and kind in ("tool_started", "tool_result")
        if measured:
            input(f"READY BEFORE REAL PUBLICATION: {eid} {kind}. Browser armed; Enter publishes: ")
        before_ms = time.time_ns() // 1_000_000
        publish(real_agent, kind, task_id, content, details)
        after_ms = time.time_ns() // 1_000_000
        if measured:
            observations.append({"engagement_id": eid, "kind": kind, "task_id": task_id,
                                 "before_publish_ms": before_ms, "after_publish_ms": after_ms})
            (OUT / "actual-publication-times.json").write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
            input(f"PUBLISHED ACTUAL {kind}. Enter resumes after browser observation: ")

    agent.event_sink = observe
    report = orchestrator.run("http://127.0.0.1:8888")
    result = {"engagement_id": eid, "execution_engine": "deterministic_baseline",
              "reported_findings": report["summary"]["total_findings"],
              "allowed": sum(len(a.allowed_actions) for a in orchestrator.agents),
              "denied": sum(len(a.denied_actions) for a in orchestrator.agents),
              "limit": "Timing/visual fixture only; baseline reported findings are not verified exploits."}
    (OUT / "timing-fixture-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result), flush=True)
finally:
    orchestrator.close()
