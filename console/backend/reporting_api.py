"""Loopback console routes for completed synthetic assessment Reporting."""

import asyncio
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import os
from tempfile import NamedTemporaryFile
from typing import Literal
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from ai.config import load_config, require_api_key
from ai.providers.reporting_sovereign import DESTINATION, MODEL, OUTPUT_TOKENS, ReportingSovereignProvider
from ai.trustgate.client import AITrustGate
from pentagi.agents.archived_reporting import compose, request_for, review_archive

Mode = Literal["local", "sovereigneg"]
RESULTS = Path(__file__).resolve().parents[2] / ".build/reporting-archive"
STALE_REPORT = "Saved report changed. Review the current report before exporting."


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Mode
    assessment_id: str | None = None


def _publish(path, report, *, exclusive=False):
    body = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    temporary = None
    try:
        with NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(body)
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
    return body


def _report_response(body, *, expected_sha256=None, filename=None):
    digest = sha256(body).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise HTTPException(409, STALE_REPORT)
    headers = {"ETag": f'"{digest}"', "Cache-Control": "no-store"}
    if filename is not None:
        encoded_filename = quote(filename, safe="")
        headers["Content-Disposition"] = (
            f'attachment; filename="{filename}"' if encoded_filename == filename
            else f"attachment; filename*=UTF-8''{encoded_filename}"
        )
    return Response(body, media_type="application/json", headers=headers)


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

    def confirm_cloud_scope(report, digest):
        current, prepared = archive_inputs(report["assessment_id"])
        if (not prepared or prepared[2] != digest or scope() != digest
                or any(current.get(field) != report.get(field)
                       for field in ("assessment_id", "source_sha256", "report_revision"))):
            raise HTTPException(409, "Archived evidence or cloud approval changed. Review the current archive.")

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
                "cloud_selection_supported": prepared is not None,
                "cloud_available": bool(digest and digest == scope() and not attempt_path(digest).exists())}

    @app.get("/reporting/archive/result")
    def archived_result(request: Request, mode: Mode = "local", download: bool = False,
                        assessment_id: str | None = None,
                        expected_sha256: str | None = Query(default=None, pattern=r"^[a-f0-9]{64}$")):
        guard_loopback(request)
        report, prepared = archive_inputs(assessment_id)
        try:
            body = result_path(report, mode).read_bytes()
        except FileNotFoundError:
            body = None
            if mode == "sovereigneg" and prepared:
                digest = prepared[2]
                try:
                    reserved = attempt_path(digest).read_bytes()
                    fallback = json.loads(reserved)
                except (ValueError, OSError):
                    fallback = None
                if (isinstance(fallback, dict) and fallback.get("status") == "degraded"
                        and fallback.get("request_sha256") == digest
                        and all(fallback.get(field) == report.get(field)
                                for field in ("assessment_id", "source_sha256", "report_revision"))):
                    body = reserved
        if body is None:
            if expected_sha256 is not None:
                raise HTTPException(409, STALE_REPORT)
            raise HTTPException(404, "No saved report in this mode")
        filename = f'{report["assessment_id"]}-{mode}.json' if download else None
        return _report_response(body, expected_sha256=expected_sha256, filename=filename)

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
                    messages, schema, digest = prepared
                    audit_id = await authorize("llm_inference", egress=True)
                    confirm_cloud_scope(report, digest)
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
                            reply = await asyncio.wait_for(
                                provider.chat(messages, max_tokens=OUTPUT_TOKENS,
                                              temperature=0, response_format=schema),
                                timeout=settings.request_timeout_s,
                            )
                            presented = compose(report, selection=reply.content)
                        except asyncio.TimeoutError:
                            presented = None
                            result["notice"] = "The cloud request reached its time limit. Showing the local evidence report."
                        except (httpx.HTTPError, ValueError, RuntimeError, TypeError, AttributeError, KeyError, OSError):
                            presented = None
                    finally:
                        await provider.close()
                    confirm_cloud_scope(report, digest)
                    if presented is not None:
                        result.update(presented, status="selected", provider=reply.provider, model=reply.model,
                                      finish_reason=reply.finish_reason,
                                      usage={"input": reply.prompt_tokens, "output": reply.completion_tokens,
                                             "reasoning": reply.reasoning_tokens,
                                             "latency_s": reply.latency_s})
                        result.pop("notice")
                body = _publish(result_path(report, payload.mode), result)
                return _report_response(body)
            finally:
                gate.close()

