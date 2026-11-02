"""Human visual acceptance of the actual scene; no screenshot/visual pass is claimed by this script."""
import argparse
from pentagi.orchestrator import EngagementOrchestrator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deny", action="store_true", help="Forbid the SQLi tool and pause on the real denial")
    options = parser.parse_args()
    orchestrator = EngagementOrchestrator(grounding_enabled=True)
    try:
        eid = orchestrator.create_engagement("human-visual-acceptance", ["127.0.0.1"], ["recon", "web-app", "network"],
            ["sql_injection_test"] if options.deny else [])
        agent = next(a for a in orchestrator.agents if a.role == "webapp_agent")
        publish = agent.event_sink
        def inspect(real_agent, kind, task_id, content, details):
            publish(real_agent, kind, task_id, content, details)
            if details.get("tool_name") == "sql_injection_test" and kind in ("tool_started", "tool_result", "tool_denied"):
                print(f"\nPublished actual {kind} for engagement {eid}. No synthetic state was inserted.")
                print("Open http://127.0.0.1:5173/ and select Web-App Agent. Inspect its monitor, Tier A, current task and raw transcript.")
                input("Capture your screenshot and record the result, then press Enter to continue: ")
        agent.event_sink = inspect
        report = orchestrator.run("http://127.0.0.1:8888")
        print("findings / allowed / denied:", report["summary"]["total_findings"],
              sum(len(a.allowed_actions) for a in orchestrator.agents), sum(len(a.denied_actions) for a in orchestrator.agents))
    finally:
        orchestrator.close()


if __name__ == "__main__":
    main()
