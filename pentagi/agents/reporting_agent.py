"""Reporting agent — MITRE ATT&CK-mapped report generation.

Aggregates verified findings from all agents and produces:
- JSON report (for console)
- Markdown report (for final writeup)
"""

import uuid
import json
from typing import Any, Dict, List
from datetime import datetime
from pentagi.agent_config import agent_config
from pentagi.call_context import prepare_context
from pentagi.engagement_context import descriptive_context, CONTEXT_LABEL
from grounding.retrieval import local_index
from pentagi.risk_plan import RiskPlan

SEVERITY_MAP = {
    "sql_injection": "Critical",
    "command_injection": "Critical",
    "path_traversal": "High",
    "xss": "Medium",
    "open_ports": "Info",
    "service_banner": "Info",
    "discovered_endpoints": "Info",
    "service_banners": "Info",
}

MITRE_NAMES = {
    "T1595": "Active Scanning",
    "T1592": "Gather Victim Host Information",
    "T1590": "Gather Victim Network Information",
    "T1190": "Exploit Public-Facing Application",
    "T1059": "Command and Scripting Interpreter",
    "T1046": "Network Service Discovery",
}


class ReportingAgent:
    """Reporting agent for MITRE ATT&CK-mapped reports."""

    def __init__(self, engagement_id: str):
        self.agent_id = f"reporting-{uuid.uuid4().hex[:8]}"
        self.role = "reporting_agent"
        self.engagement_id = engagement_id
        self.capability_contract = agent_config(self.role)
        self.model_tier = self.capability_contract["model_tier"]
        self.model_name = self.capability_contract["model_name"]
        self.grounding_enabled = False
        self.last_call_context = None
        self.mitre_techniques = ["T1595", "T1592", "T1590", "T1190", "T1059", "T1046"]

    def generate_report(self, findings: List[Dict], target: str, engagement_id: str, engagement_context=None) -> Dict:
        """Generate a structured report from verified findings."""
        report_findings = []
        self.last_call_context = prepare_context(self.role,
            "MITRE ATT&CK mapping, evidence collection and remediation reporting for " + ", ".join(f.get("type", "") for f in findings),
            self.capability_contract, self.grounding_enabled)
        for f in findings:
            finding_type = f.get("type", "unknown")
            mitre_id = f.get("mitre", "Unknown")
            report_findings.append({
                "id": f.get("id", f"finding-{len(report_findings)+1}"),
                "type": finding_type,
                "severity": SEVERITY_MAP.get(finding_type, "Info"),
                "mitre_id": mitre_id,
                "mitre_name": MITRE_NAMES.get(mitre_id, "Unknown"),
                "agent": f.get("agent", "unknown"),
                "target": f.get("target", target),
                "evidence": f.get("data", {}),
                "verified": f.get("verified", False),
                "verification": f.get("verification"),
                "reproduction_steps": self._reproduction_steps(finding_type, f.get("data", {})),
            })

        # Sort by severity
        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
        report_findings.sort(key=lambda x: severity_order.get(x["severity"], 5))

        # MITRE coverage
        techniques_found = set(f.get("mitre", "") for f in findings)
        mitre_coverage = {
            tid: MITRE_NAMES.get(tid, "Unknown")
            for tid in techniques_found
            if tid in MITRE_NAMES
        }

        report = {
            "engagement_id": engagement_id,
            "target": target,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_findings": len(report_findings),
                "critical": sum(1 for f in report_findings if f["severity"] == "Critical"),
                "high": sum(1 for f in report_findings if f["severity"] == "High"),
                "medium": sum(1 for f in report_findings if f["severity"] == "Medium"),
                "info": sum(1 for f in report_findings if f["severity"] == "Info"),
            },
            "mitre_coverage": mitre_coverage,
            "findings": report_findings,
            "generation_context": self.last_call_context,
            "narrative_context": descriptive_context(engagement_context),
            "context_label": CONTEXT_LABEL,
            "mitigation_plan": self._mitigation_plan(findings=findings),
        }

        return report

    def generate_direct_mitigation(self, risk_plan):
        """Option A: the existing report builder, no agent loop or model/tool call."""
        plan = RiskPlan.model_validate(risk_plan).model_dump()
        report = self.generate_report([], 'No target access — Option A', self.engagement_id, plan['context'])
        report.update(option='A', execution_engine='offline_reporting', risk_plan=plan,
            evidence_label='Hypothetical context matches only. No live testing or verified findings.',
            target_accessed=False, mitigation_plan=self._mitigation_plan(risks=plan['risks']))
        return report

    def _mitigation_plan(self, findings=(), risks=None):
        """Shared deterministic synthesis; retrieved references never become authority."""
        hypothetical = risks is not None
        # Trust the existing runtime's proof envelope, not model narrative/candidate flags.
        verified = []
        for finding in findings:
            proof = finding.get('verification')
            if (finding.get('verified') is True and isinstance(proof, dict)
                    and isinstance(proof.get('result'), dict) and proof['result'].get('supported') is True
                    and proof.get('audit_entry_id')):
                verified.append(finding)
        basis = 'hypothetical_risk_plan' if hypothetical else ('verified_findings' if verified else 'no_verified_findings')
        recommendations = []
        for item in (risks if hypothetical else verified):
            query = item['reference']['name'] if hypothetical else item['type'].replace('_',' ')+' web application remediation'
            refs = [item['reference']] if hypothetical else local_index().retrieve(query, self.model_tier, limit=2)
            title, action = self._mitigation_text(query)
            recommendations.append({'id':'mitigation_'+item['id'], 'title':title, 'action':action,
                'evidence_basis':basis, 'risk_ids':[item['id']] if hypothetical else [],
                'finding_ids':[] if hypothetical else [item['id']],
                'references':[{k:ref[k] for k in ('id','framework','name','source_url','description')} for ref in refs],
                'uncertainty':'Applicability requires review; this recommendation is not evidence of an implemented or effective control.'})
        return {'schema_version':1, 'option':'A' if hypothetical else 'B', 'evidence_basis':basis,
            'method':'Shared deterministic Reporting templates with local framework references; no additional model inference.',
            'reference_retrieval':'Post-report local retrieval, separate from agent grounding-on/off inference conditions.',
            'verified_finding_count':len(verified), 'hypothetical_risk_count':len(risks or []),
            'recommendations':recommendations,
            'limits':'Hypotheses are not findings. References support review, not authorization or proof that a control works.'}

    @staticmethod
    def _mitigation_text(query):
        query = query.lower()
        if any(word in query for word in ('injection','xss','public-facing','public facing')):
            return ('Harden input processing', 'Use parameterized queries, contextual output encoding and strict input validation. Remove shell interpolation; keep exposed application dependencies patched. Validate the relevant control in an authorized follow-up.')
        if any(word in query for word in ('access','privilege','traversal','authorization')):
            return ('Enforce least privilege and resource boundaries', 'Check authorization on every object and operation. Restrict filesystem paths to approved roots and deny by default. Review service-account permissions and test tenant isolation in an authorized follow-up.')
        if any(word in query for word in ('credential','authentication','identity','password')):
            return ('Strengthen identity controls', 'Require phishing-resistant MFA where supported, rotate exposed credentials and limit service-account privileges. Review session expiry and authentication monitoring.')
        if any(word in query for word in ('storage','cryptograph','database','data protection')):
            return ('Protect stored data', 'Classify retained data, minimize retention, restrict database roles and review encryption/key management and restore tests. Confirm applicability before implementation.')
        if any(word in query for word in ('network','scan','service','port')):
            return ('Reduce and monitor exposed services', 'Inventory exposed listeners, remove unnecessary services, segment access and patch supported versions. Alert on unexpected connections; verify changes in an authorized follow-up.')
        return ('Review layered preventive and detective controls', 'Identify the assets and trust boundaries relevant to the referenced technique. Review patching, least privilege and application/security logs; assign an owner and validate chosen controls in an authorized follow-up.')

    def _reproduction_steps(self, finding_type: str, data: dict) -> List[str]:
        """Generate reproduction steps for a finding."""
        if data.get("marker"):
            endpoint = {"xss": "/search?q=", "path_traversal": "/file?path=", "command_injection": "/ping?host=", "sql_injection": "/login username="}.get(finding_type, "")
            return ["Use the authorized local lab only", f"Request {endpoint}{data.get('payload', '')}",
                f"Confirm the recorded response evidence for marker {data['marker']}; see the independent second-request verification",
                "XSS evidence is raw HTML script reflection; browser execution was not checked" if finding_type == "xss" else "Do not substitute real sensitive files or destructive payloads"]
        steps = {
            "sql_injection": [
                "Navigate to the login page",
                "Enter SQL injection payload in username field: ' OR 1=1 --",
                "Submit the form",
                "Observe unauthorized access or error message",
            ],
            "xss": [
                "Navigate to the search page",
                "Enter XSS payload: <script>alert(1)</script>",
                "Submit the search",
                "Observe script execution in the response",
            ],
            "command_injection": [
                "Navigate to the ping utility",
                "Enter command injection payload: 127.0.0.1; whoami",
                "Submit the form",
                "Observe command output in the response",
            ],
            "path_traversal": [
                "Navigate to the file viewer",
                "Enter path traversal payload: ../../etc/passwd",
                "Submit the request",
                "Observe file contents in the response",
            ],
            "open_ports": [
                "Run TCP connect scan against target",
                "Identify open ports from scan results",
                "Verify each open port responds to connection",
            ],
            "service_banner": [
                "Connect to identified open ports",
                "Send probe request",
                "Capture and analyze service banner",
            ],
            "discovered_endpoints": [
                "Crawl common paths on target",
                "Record HTTP status codes and response sizes",
                "Identify accessible endpoints for further testing",
            ],
            "service_banners": [
                "Connect to each open port",
                "Send service probe",
                "Capture banner responses",
            ],
        }
        return steps.get(finding_type, ["Manual verification required"])

    def to_markdown(self, report: Dict) -> str:
        """Convert report to Markdown format."""
        lines = []
        lines.append(f"# Security Assessment Report")
        lines.append(f"")
        lines.append(f"**Engagement ID:** {report['engagement_id']}")
        lines.append(f"**Target:** {report['target']}")
        lines.append(f"**Generated:** {report['generated_at']}")
        lines.append(f"")
        if report.get('narrative_context'):
            lines.extend(['## Descriptive engagement context', '', report['context_label'], ''])
            for key, value in report['narrative_context'].items():
                lines.append(f"- {key.replace('_', ' ').title()}: {json.dumps(value, ensure_ascii=False)}")
            lines.append('')
        completion = report.get('assessment_completion')
        if completion:
            lines.extend(['## Assessment coverage', '', completion['notice'], ''])
            for outcome in completion['specialist_outcomes']:
                lines.append(f"- {outcome['role']}: {outcome['status']}" +
                             (f" - {outcome['error']}" if outcome.get('error') else ''))
                coverage = outcome.get('coverage')
                if coverage:
                    lines.append(f"  - Catalogue coverage: {'complete' if coverage['complete'] else 'incomplete'}; stop: {coverage.get('stop_reason', 'unknown')}")
                    lines.append("  - Untested tools: " + (", ".join(coverage.get('untested_tools', [])) or "none recorded"))
                    for issue in coverage.get('tool_errors', []):
                        lines.append(f"  - Execution error ({issue['tool']}): {issue['error']}")
                    for issue in coverage.get('verification_issues', []):
                        lines.append(f"  - Verification issue ({issue['tool']}): {issue['reason']}")
                    if coverage.get('denied_tools'):
                        lines.append("  - Denied tools: " + ", ".join(coverage['denied_tools']))
            lines.append('')
        lines.append(f"## Summary")
        lines.append(f"")
        s = report['summary']
        lines.append(f"- Total findings: {s['total_findings']}")
        lines.append(f"- Critical: {s['critical']}")
        lines.append(f"- High: {s['high']}")
        lines.append(f"- Medium: {s['medium']}")
        lines.append(f"- Info: {s['info']}")
        lines.append(f"")
        lines.append(f"## MITRE ATT&CK Coverage")
        lines.append(f"")
        for tid, name in report['mitre_coverage'].items():
            lines.append(f"- {tid}: {name}")
        lines.append(f"")
        lines.append(f"## Findings")
        lines.append(f"")
        for f in report['findings']:
            lines.append(f"### {f['id']}: {f['type']} ({f['severity']})")
            lines.append(f"")
            lines.append(f"- **MITRE:** {f['mitre_id']} — {f['mitre_name']}")
            lines.append(f"- **Agent:** {f['agent']}")
            lines.append(f"- **Target:** {f['target']}")
            lines.append(f"")
            lines.append(f"**Reproduction steps:**")
            for i, step in enumerate(f['reproduction_steps'], 1):
                lines.append(f"{i}. {step}")
            lines.append(f"")
        plan = report.get('mitigation_plan')
        if plan:
            lines.extend(['## Mitigation plan', '', f"Evidence basis: {plan['evidence_basis']}", '', plan['method'], '', plan['limits'], ''])
            if not plan['recommendations']:
                lines.extend(['No evidence-backed or context-matched recommendations available. This is not an absence-of-risk claim.', ''])
            for recommendation in plan['recommendations']:
                lines.extend([f"### {recommendation['title']}", '', recommendation['action'], '', recommendation['uncertainty'], ''])
                for reference in recommendation['references']:
                    lines.append(f"- Reference {reference['id']}: {reference['name']} — {reference['source_url']}")
                lines.append('')
        return "\n".join(lines)

    def save_report(self, report: Dict, output_dir: str = "."):
        """Save report as both JSON and Markdown."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        eid = report['engagement_id'][:8]

        json_path = os.path.join(output_dir, f"report_{eid}.json")
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        md_path = os.path.join(output_dir, f"report_{eid}.md")
        with open(md_path, "w") as f:
            f.write(self.to_markdown(report))

        return json_path, md_path
