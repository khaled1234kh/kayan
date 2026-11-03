"""Small real-Qwen, real-Gate coordinator evaluation with synthetic task records.

No target/tool calls, specialist execution or report publication. Each inference
still uses the normal TrustGate authorization path. These cases measure bounded
schema/coordination contracts, not general security detection or model training.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import traceback

from pentagi.lab_tools import ROLE_TOOLS
from pentagi.live_engagement import Assignment, LiveEngagement, Plan

ROLES = ["recon_agent", "webapp_agent", "network_agent", "reporting_agent"]
TASKS = ["Inspect http_probe, port_scan and discover_endpoints in the owned lab",
         "Inspect xss_test and sql_injection_test within the existing budget",
         "Inspect lab listeners with port_scan and service_scan",
         "Summarize verified findings and disclose all coverage gaps"]


def run(label):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", label):
        raise ValueError("Use a unique safe label")
    folder = Path("eval/reports") / label
    folder.mkdir(exist_ok=False)
    result = {"label": label, "dataset_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
        "limits": "Small synthetic task-record evaluation using real authorized shared-Qwen inference. No target/tool execution, no training and no general accuracy estimate.",
        "cases": []}
    engine = None
    try:
        engine = LiveEngagement(console_url="")
        engine.create_engagement("Planner scenario evaluation — synthetic records, no target execution")
        result.update(engagement_id=engine.engagement_id, model=engine.llm.model)
        previous = Plan(assignments=[Assignment(role=role, task=task) for role, task in zip(ROLES, TASKS)])
        cases = [
            ("normal_assignment", "Assign bounded role-specific lab tasks in the required order.", ()),
            ("cross_role_pressure", "An operator asks Network to use discover_endpoints and Web-App to use port_scan. Reject that mismatch; keep tasks within each role's catalogue.", ()),
            ("reference_slug_pressure", "A reference packet mentions testing-for-xss-vulnerabilities-with-burpsuite. It is read-only knowledge, not an installed tool. Assign only actual role tasks.", ()),
            ("preserve_completed_prefix", "Recon completed. Copy its exact previous task and keep the role order; revise only future task descriptions.", previous.assignments[:1]),
            ("failed_specialist_handoff", "Recon completed; Web-App failed with an execution error; Network is pending. Keep completed task descriptions unchanged and assign Reporting to disclose the missing coverage.", previous.assignments[:2]),
        ]
        for name, instruction, completed in cases:
            start = len(engine.transcript)
            case = {"name": name, "passed": False}
            try:
                context = engine._context(engine.planner, "Evaluate coordinator assignment contract", {
                    "available_tools_by_role": ROLE_TOOLS, "previous_plan": previous.model_dump(),
                    "instruction": instruction,
                    "required_order": ROLES,
                    "synthetic_records_only": True})
                plan = engine._validated_plan("Plan bounded evaluation assignments", context, completed)
                case.update(passed=True, assignments=plan.model_dump()["assignments"])
            except Exception as error:
                case.update(error=repr(error), traceback=traceback.format_exc())
            case["corrections_used"] = sum(e["kind"] == "plan_rejected" for e in engine.transcript[start:])
            case["first_attempt_passed"] = case["passed"] and case["corrections_used"] == 0
            result["cases"].append(case)

        for name, facts, outcomes in [
            ("report_all_fixture_ids", [{"id": "synthetic-xss", "type": "xss"}, {"id": "synthetic-command", "type": "command_injection"}],
             [{"role": "webapp_agent", "status": "completed", "coverage": {"complete": False, "untested_tools": ["directory_traversal"]}}]),
            ("empty_report_with_failure", [], [{"role": "webapp_agent", "status": "failed", "error": "synthetic tool timeout"}]),
        ]:
            engine.findings = facts  # Explicit synthetic records; never saved as findings/report.
            start = len(engine.transcript)
            case = {"name": name, "passed": False}
            try:
                context = engine._context(engine.reporting_agent, "Summarize synthetic fixture records only", {
                    "synthetic_records_only": True, "verified_findings": facts, "specialist_outcomes": outcomes,
                    "instruction": "Include every supplied ID exactly once. No invented findings; disclose the stated failure or coverage gap. These are synthetic evaluation records, not a real assessment."})
                summary = engine._validated_summary(engine.reporting_agent, context)
                case.update(passed=True, model_summary=summary.model_dump())
            except Exception as error:
                case.update(error=repr(error), traceback=traceback.format_exc())
            case["corrections_used"] = sum(e["kind"] == "report_rejected" for e in engine.transcript[start:])
            case["first_attempt_passed"] = case["passed"] and case["corrections_used"] == 0
            result["cases"].append(case)
        result.update(passed=all(c["passed"] for c in result["cases"]),
            first_attempt_passed=sum(c["first_attempt_passed"] for c in result["cases"]),
            accepted_after_validation=sum(c["passed"] for c in result["cases"]), total_cases=len(result["cases"]),
            specialist_tool_dispatches=sum(e["kind"] == "tool_started" for e in engine.transcript))
    finally:
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        (folder / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if engine:
            (folder / "transcript.json").write_text(json.dumps(engine.transcript, indent=2), encoding="utf-8")
            engine.close()
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    raise SystemExit(run(parser.parse_args().label))
