"""Loopback console routes for completed synthetic assessment Reporting."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import os
from tempfile import NamedTemporaryFile
from typing import Literal

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from ai.config import load_config, require_api_key
from ai.providers.reporting_sovereign import DESTINATION, MODEL, OUTPUT_TOKENS, ReportingSovereignProvider
from ai.trustgate.client import AITrustGate
from pentagi.agents.archived_reporting import compose, request_for, review_archive

Mode = Literal["local", "sovereigneg"]
RESULTS = Path(__file__).resolve().parents[2] / ".build/reporting-archive"


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Mode
    assessment_id: str | None = None


def _publish(path, report, *, exclusive=False):
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(report, file, ensure_ascii=False, indent=2)
            if exclusive:
                file.flush()
                os.fsync(file.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install_reporting_api(app, *, load_archive=review_archive, output=RESULTS,
                          make_gate=AITrustGate, make_provider=ReportingSovereignProvider,
                          approved_scope=None, catalog=None):
    lock = asyncio.Lock()

    def guard_loopback(request):
        loopback = ("127.0.0.1", "::1", "localhost")
        if request.url.hostname not in loopback or not request.client or request.client.host not in loopback:
            raise HTTPException(403, "Archived Reporting is available only from the loopback console")

    def archive_inputs(assessment_id=None):
        try:
            if catalog is not None:
                report = catalog.load(assessment_id)
            else:
                report = load_archive()
                if assessment_id not in (None, report["assessment_id"]):
                    raise LookupError(assessment_id)
            return report, None if report.get("custody_test_only") else request_for(report)
        except LookupError:
            raise HTTPException(404, "Completed synthetic assessment not found") from None
        except (ValueError, OSError):
            raise HTTPException(409, "Saved synthetic archive failed verification") from None

    def scope():
        # An operator supplies the specifically approved request digest and
        # confirms Student-only account controls outside the application.
        return (os.environ.get("KAYAN_REPORTING_APPROVED_SHA256")
                if approved_scope is None else approved_scope)

    def attempt_path(digest):
        return output / f"attempt-{digest}.lock"

    def result_path(report, mode):
        revision = report.get("report_revision", report["source_sha256"])
        return output / f"{revision}-{mode}.json"

    @app.get("/reporting/assessments")
    def completed_assessments(request: Request):
        guard_loopback(request)
        if catalog is not None:
            return catalog.assessments()
        report, _ = archive_inputs()
        return [{"assessment_id": report["assessment_id"], "title": report["title"]}]

    @app.get("/reporting/archive")
    def archived_assessment(request: Request, assessment_id: str | None = None):
        guard_loopback(request)
        report, prepared = archive_inputs(assessment_id)
        digest = prepared[2] if prepared else None
        return {"assessment_id": report["assessment_id"], "title": report["title"],
                "request_sha256": digest, "cloud_model": MODEL,
                "verification": report.get("verification", "fixture_custody"),
                "coverage": report.get("coverage", {}),
                "source_status": report.get("source_status", "fixture"),
                "review_status": report.get("review_status"),
                "admission_status": report.get("admission_status"),
                "custody_test_only": report.get("custody_test_only", False),
                "cloud_available": bool(digest and digest == scope() and not attempt_path(digest).exists())}

    @app.get("/reporting/archive/result")
    def archived_result(request: Request, mode: Mode = "local", download: bool = False, assessment_id: str | None = None):
        guard_loopback(request)
        report, prepared = archive_inputs(assessment_id)
        path = result_path(report, mode)
        if not path.is_file():
            if mode != "sovereigneg" or not prepared:
                raise HTTPException(404, "No saved report in this mode")
            digest = prepared[2]
            path = attempt_path(digest)
            try:
                fallback = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                fallback = None
            if (not isinstance(fallback, dict) or fallback.get("status") != "degraded"
                    or fallback.get("request_sha256") != digest
                    or any(fallback.get(field) != report.get(field)
                           for field in ("assessment_id", "source_sha256", "report_revision"))):
                raise HTTPException(404, "No saved report in this mode")
            if not download:
                return fallback
        if download:
            return FileResponse(path, media_type="application/json",
                                filename=f'{report["assessment_id"]}-{mode}.json')
        return json.loads(path.read_text(encoding="utf-8"))

    @app.post("/reporting/archive/run")
    async def run_archived_reporting(request: Request, payload: ReportRequest):
        guard_loopback(request)
        async with lock:
            report, prepared = archive_inputs(payload.assessment_id)
            if payload.mode == "sovereigneg" and (
                not prepared or prepared[2] != scope() or attempt_path(prepared[2]).exists()
            ):
                raise HTTPException(409, "No unused approval for this exact synthetic cloud report")
            try:
                config = load_config(load_env=False)
                gate = make_gate(config.trustgate)
            except (KeyError, ValueError, OSError):
                raise HTTPException(503, "Reporting governance configuration is unavailable") from None

            async def authorize(action, *, egress=False):
                args = {"purpose": "synthetic_archived_reporting", "archive_sha256": report["source_sha256"]}
                if egress:
                    args.update(provider="sovereigneg", model=MODEL, destination=DESTINATION,
                                request_sha256=prepared[2])
                decision = await gate.authorize(
                    engagement_id=report.get("authorization_id", report["assessment_id"]), agent_id="reporting_agent",
                    agent_role="reporting_agent", action=action, technique="reporting",
                    target="127.0.0.1", tool_args=args,
                )
                if not decision.allowed:
                    raise HTTPException(403, f"TrustGate denied {action}")
                return decision.audit_entry_id

            try:
                write_audit = await authorize("write_report")
                result = compose(report)
                result.update(status="local", provider=None, model=None, audit={"write_report": write_audit})
                output.mkdir(parents=True, exist_ok=True)
                if payload.mode == "sovereigneg":
                    audit_id = await authorize("llm_inference", egress=True)
                    result["audit"]["llm_inference"] = audit_id
                    configured = config.get_provider("sovereigneg")
                    settings = replace(configured, max_retries=1, max_concurrency=1,
                                       max_tokens=OUTPUT_TOKENS, request_timeout_s=min(60, configured.request_timeout_s))
                    try:
                        key = require_api_key(settings)
                        provider = make_provider(settings, api_key=key)
                    except (ValueError, RuntimeError, KeyError):
                        raise HTTPException(503, "SovereignEG Reporting is not configured") from None
                    try:
                        messages, schema, digest = prepared
                        result.update(status="degraded", attempted_provider="sovereigneg", attempted_model=MODEL,
                                      request_sha256=digest,
                                      notice="No verified cloud response is available. Showing the local evidence report.")
                        try:
                            # The one-shot reservation also holds the recoverable local
                            # report. Both become visible together, before any egress.
                            _publish(attempt_path(digest), result, exclusive=True)
                        except FileExistsError:
                            raise HTTPException(409, "The approved cloud request has already been attempted") from None
                        try:
                            reply = await provider.chat(messages, max_tokens=OUTPUT_TOKENS,
                                                        temperature=0, response_format=schema)
                            presented = compose(report, selection=reply.content)
                        except (httpx.HTTPError, ValueError, RuntimeError, TypeError, AttributeError, KeyError, OSError):
                            presented = None
                        if presented is not None:
                            result.update(presented, status="selected", provider=reply.provider, model=reply.model,
                                          finish_reason=reply.finish_reason,
                                          usage={"input": reply.prompt_tokens, "output": reply.completion_tokens,
                                                 "reasoning": reply.reasoning_tokens,
                                                 "latency_s": reply.latency_s})
                            result.pop("notice")
                        _publish(result_path(report, payload.mode), result)
                    finally:
                        await provider.close()
                else:
                    _publish(result_path(report, payload.mode), result)
                return result
            finally:
                gate.close()

