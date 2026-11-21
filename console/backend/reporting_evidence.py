"""Read-only import of completed local synthetic sessions for defensive Reporting."""

from hashlib import sha256
import json
import os
from pathlib import Path
import re
from sqlite3 import Error as ReceiptStoreError
from tempfile import NamedTemporaryFile

from console.backend.reporting_exchange import SignedExchange
from pentagi.execution_evidence import ToolEvidenceStore
from pentagi.agents.archived_reporting import ARCHIVE, ARCHIVE_SHA256, review_archive, review_archive_document

SLATE_ID = "synthetic-slate-reporting"
ROOT = Path(__file__).resolve().parents[2]
VERSION = "kayan.assessment-evidence/1"
UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
ROLES = frozenset(("recon_agent", "webapp_agent", "network_agent"))
TECHNIQUE = re.compile(r"T[0-9]{4}(?:\.[0-9]{3})?")


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def digest(raw):
    return sha256(raw).hexdigest()


def eligible(state):
    return (
        UUID.fullmatch(str(state.get("engagement_id", ""))) is not None
        and state.get("status") == "completed"
        and state.get("execution_engine") == "local_llm"
        and state.get("target") == "http://127.0.0.1:8888"
        and (state.get("roe") or {}).get("targets") == ["127.0.0.1"]
    )


def _decision_scope(row):
    return row.get("agent_role"), row.get("task_id"), row.get("tool_name"), row.get("target")


def _decision_identity(row):
    values = [row.get("decision"), row.get("trustgate_decision")]
    if any(value is not None and not isinstance(value, str) for value in values):
        return None
    decisions = {value.upper() for value in values if value}
    if len(decisions) != 1:
        return None
    return row.get("agent_id"), decisions.pop(), row.get("audit_entry_id") or None


def _conflicting_decisions(entries):
    seen, conflicts = {}, set()
    for row in entries:
        if row.get("agent_role") not in ROLES or row.get("kind") != "authorization_decision" or not row.get("task_id"):
            continue
        task = _decision_scope(row)
        identity = _decision_identity(row)
        if identity is None or seen.setdefault(task, identity) != identity:
            conflicts.add(task)
    return conflicts


def capture(state, source_store=None):
    """Capture recorded outcomes without claiming the operator logs are custody."""
    if not eligible(state):
        raise ValueError("Assessment is outside the completed owned-lab scope")
    eid = state["engagement_id"]
    entries = [row for row in state.get("transcript", []) if row.get("engagement_id") == eid]
    decisions, records, outcomes = {}, {}, {}
    invalid_sources = 0
    # Consider conflicts anywhere in the completed transcript. The chronological
    # pass still requires a decision observed before the captured outcome.
    conflicting_decisions = _conflicting_decisions(entries)
    for row in entries:
        role, kind = row.get("agent_role"), row.get("kind")
        task = _decision_scope(row)
        if role in ROLES and kind == "authorization_decision" and task[1]:
            decisions[task] = row
        elif role in ROLES and kind in ("tool_result", "tool_denied") and (
            "source_artifact_sha256" in row or row.get("source_capture_failed")
        ):
            try:
                sha = row["source_artifact_sha256"]
                source = (source_store or ToolEvidenceStore()).load(eid, row["task_id"], sha)
                decision = _decision_identity(decisions[task])
                if (task in conflicting_decisions or source["tool"] != row["tool_name"] or source["agent"] != row["agent_id"]
                        or source["role"] != role
                        or decision != (source["agent"], source["authorization_decision"], source["audit_entry_id"])
                        or row.get("target") != "127.0.0.1"
                        or (kind == "tool_denied") != (source["status"] == "denied")
                        or source["source_id"] in records):
                    raise ValueError("Capture does not match the execution event")
                records[source["source_id"]] = {
                    "source_id": source["source_id"], "revision": 1, "sha256": source["output_sha256"],
                    "artifact_sha256": sha, "occurrence": source["task_id"], "agent": role,
                    "tool": source["tool"], "target": source["approved_target"],
                    "completed_at": source["completed_at"], "outcome": source["outcome"],
                    "failed": source["status"] != "completed", "truncated": source["output_projected"],
                    "status": source["status"], "authorization_status": "recorded decision",
                    "decision": source["authorization_decision"], "audit_entry_id": source["audit_entry_id"],
                    "attribution_status": "unreviewed",
                }
            except (ValueError, OSError, TypeError, KeyError):
                invalid_sources += 1
        elif role in ROLES and kind == "tool_result" and isinstance(row.get("id"), str):
            source_id = row["id"]
            decision = decisions.get(task, {})
            outcome = row.get("result")
            content = outcome.encode("utf-8") if isinstance(outcome, str) else canonical(outcome)
            record = {
                "source_id": source_id, "revision": 1, "sha256": digest(content),
                "occurrence": task[1], "agent": role, "tool": row.get("tool_name"),
                "target": row.get("target"), "timestamp_ms": row.get("timestamp"),
                "outcome": outcome, "failed": bool(row.get("error")),
                "truncated": bool(row.get("truncated")),
                "authorization_status": "recorded decision" if decision.get("audit_entry_id") else "unavailable",
                "decision": decision.get("trustgate_decision") or decision.get("decision"),
                "audit_entry_id": decision.get("audit_entry_id"), "attribution_status": "unreviewed",
            }
            if source_id in records and records[source_id] != record:
                raise ValueError("Conflicting execution record ID")
            records[source_id] = record
        elif role == "planner_agent" and kind == "specialist_outcome":
            outcome = row.get("specialist_outcome", {})
            if outcome.get("role") in ROLES:
                outcomes[outcome["role"]] = outcome
    techniques = {finding.get("mitre") or finding.get("mitre_id") or "" for finding in state.get("findings", [])}
    techniques = sorted({value if isinstance(value, str) and TECHNIQUE.fullmatch(value) else "Unmapped"
                         for value in techniques})
    captured_count = sum("artifact_sha256" in row for row in records.values())
    source_status = ("invalid_source" if invalid_sources else
                     "mixed_source" if 0 < captured_count < len(records) else
                     "source_captured" if captured_count else "transcript_only" if records else "no_evidence")
    result = {
        "version": VERSION, "assessment_id": eid, "engagement_id": eid,
        "target": state["target"], "started_at": state.get("start_time"), "completed_at": state.get("end_time"),
        "record_origin": "completed owned-lab session transcript", "records": list(records.values()),
        "specialist_outcomes": list(outcomes.values()), "unreviewed_hypotheses": techniques,
    }
    if captured_count or invalid_sources:
        result.update(version="kayan.assessment-evidence/2", record_origin="tool boundary and saved session",
                      source_status=source_status, invalid_sources=invalid_sources)
    return result


class ReportingCatalog:
    def __init__(self, sessions, directory, source_store=None):
        self.sessions = sessions
        self.directory = Path(directory)
        self.source_store = source_store
        self.reviews_directory = self.directory.parent / "reviews"
        self.exchange = SignedExchange(self, self.reviews_directory)

    def assessments(self):
        rows = [{"assessment_id": SLATE_ID, "title": "Slate archive and recovery review"}]
        for state in self.sessions.completed():
            if eligible(state):
                eid = state["engagement_id"]
                rows.append({"assessment_id": eid, "title": f"Owned lab · {eid[:8]}"})
        return rows

    def _snapshot(self, state):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f'{state["engagement_id"]}.json'
        body = canonical(capture(state, self.source_store))
        # Each distinct byte representation gets a separate immutable revision.
        path = path.with_name(f"{path.stem}-{digest(body)}.json")
        if not path.exists():
            with NamedTemporaryFile(dir=path.parent, delete=False) as pending:
                temporary = Path(pending.name)
                pending.write(body)
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
            finally:
                temporary.unlink(missing_ok=True)
        if path.read_bytes() != body:
            raise ValueError("Saved Reporting evidence changed")
        return json.loads(body), digest(body)

    def _submitted_reviews(self, assessment_id, source_digest):
        reviews = set()
        for path in self.reviews_directory.glob("*.json"):
            try:
                raw = path.read_bytes()
                check = digest(raw)
                doc = json.loads(raw)
                if (path.stem.endswith("-" + check) and doc["assessment_id"] == assessment_id
                        and doc["source_sha256"] == source_digest
                        and doc["status"] == "submitted_awaiting_independent_admission"):
                    reviews.add(check)
            except (ValueError, OSError, TypeError, KeyError):
                continue
        return reviews

    def _custody(self, snapshot, source_digest):
        location, pin = (os.environ.get(name) for name in (
            "KAYAN_REPORTING_CUSTODY_FILE", "KAYAN_REPORTING_CUSTODY_SHA256",
        ))
        if not location and not pin:
            return None
        if not location or not pin:
            raise ValueError("Custody catalogue configuration is incomplete")
        path = Path(location).resolve(strict=True)
        if path.is_relative_to(ROOT):
            raise ValueError("Custody catalogue must be outside the checkout")
        raw = path.read_bytes()
        if digest(raw) != pin:
            raise ValueError("Custody catalogue integrity check failed")
        eid = snapshot["assessment_id"]
        package = json.loads(raw).get(eid)
        if package is None:
            return None
        return self.evaluate_package(snapshot, source_digest, package)

    @staticmethod
    def evaluate_package(snapshot, source_digest, package):
        eid = snapshot["assessment_id"]
        if (package["assessment_id"] != eid or json.loads(package["snapshot"])["case_id"] != eid
                or package["operational_evidence_sha256"] != source_digest):
            raise ValueError("Custody assignment does not match the selected assessment revision")
        records = {(row["source_id"], row["revision"]): row for row in snapshot["records"]}
        for record in package["records"]:
            reference = records.get((record["id"], record["revision"]))
            if (not reference or reference["truncated"] or reference.get("failed")
                    or (snapshot["version"] != VERSION and "artifact_sha256" not in reference)
                    or digest(record["text"].encode("utf-8")) != reference["sha256"]):
                raise ValueError("Custody source does not match the captured record")
        return {**review_archive_document(package, source_digest, include_bindings=snapshot["version"] != VERSION),
                "report_revision": digest(canonical(package))}

    def review_inputs(self, assessment_id):
        if not UUID.fullmatch(assessment_id):
            raise KeyError(assessment_id)
        state = self.sessions.load(assessment_id)
        if state is None or not eligible(state):
            raise KeyError(assessment_id)
        return self._snapshot(state)

    def load(self, assessment_id):
        if assessment_id in (None, SLATE_ID):
            return {**review_archive(ARCHIVE, ARCHIVE_SHA256), "verification": "fixture_custody", "source_status": "fixture",
                    "coverage": {"recorded_tools": 4}}
        snapshot, sha = self.review_inputs(assessment_id)
        submitted = self._submitted_reviews(assessment_id, sha)
        try:
            if snapshot.get("invalid_sources"):
                raise ValueError("Source capture failed integrity checks")
            reviewed = (self._custody(snapshot, sha) if snapshot["version"] == VERSION
                        else self.exchange.evaluate_current(assessment_id))
            verification = "independent_custody" if reviewed else "missing_custody"
        except (LookupError, TypeError, ValueError, OSError, ReceiptStoreError):
            reviewed = None
            verification = "invalid_custody"

        recorded = {outcome["role"]: outcome for outcome in snapshot["specialist_outcomes"]}
        coverage = {
            "recorded_tools": len(snapshot["records"]),
            "invalid_sources": snapshot.get("invalid_sources", 0),
            "captured_tools": sum("artifact_sha256" in row for row in snapshot["records"]),
            "failed_tools": sum(record["failed"] for record in snapshot["records"]),
            "truncated_tools": sum(record["truncated"] for record in snapshot["records"]),
            "specialists": [{"role": role, "status": recorded.get(role, {}).get("status", "unavailable"),
                             "complete": recorded.get(role, {}).get("coverage", {}).get("complete") is True,
                             "stop_reason": recorded.get(role, {}).get("coverage", {}).get("stop_reason")}
                            for role in sorted(ROLES)],
        }
        if reviewed is None:
            reviewed = {
                "title": f"Owned lab · {assessment_id[:8]}", "source_sha256": sha, "assessment_id": assessment_id,
                "findings": [], "withheld": [], "report_revision": digest(canonical([sha, verification])),
                "limitation": "Recorded outcomes are available. Verified findings require independent custody, attribution and authorization review.",
            }
        # Preserve runtime candidates absent from the independently reviewed package.
        classified = {row["technique"] for key in ("findings", "withheld") for row in reviewed[key]}
        return {
            **reviewed, "verification": verification, "coverage": coverage,
            "review_status": ("verified" if verification == "independent_custody" else "submitted" if submitted else "awaiting"),
            "admission_status": reviewed.get("admission_status", "evaluated" if verification == "independent_custody" else "pending"),
            "source_status": snapshot.get("source_status", "transcript_only" if snapshot["records"] else "no_evidence"),
            "authorization_id": f"archived-{assessment_id}", "bind_request_to_assessment": True,
            "withheld": [*reviewed["withheld"], *(
                {"technique": tid, "reasons": ["independent_custody_missing" if verification == "missing_custody"
                                               else "independent_evidence_not_admitted"]}
                for tid in snapshot["unreviewed_hypotheses"] if tid not in classified
            )],
        }

