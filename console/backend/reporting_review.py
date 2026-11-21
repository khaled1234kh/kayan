"""Scoped human review drafts for captured evidence. Drafts grant no admission."""

from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
from sqlite3 import Error as ReceiptStoreError
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Literal

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from console.backend.reporting_exchange import Receipt, canonical
from console.backend.reporting_identity import authenticate
from eval.attack_evidence_guard_v3 import MECHANICS


class AssertionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=100)
    technique: str
    role: Literal["actor", "authorization", "mechanic", "outcome", "process_session"]
    value: str | None = Field(default=None, max_length=100)
    disposition: Literal["supported", "contradicted", "unresolved"]
    occurrence: str | None = Field(default=None, min_length=1, max_length=128, strict=True)


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_id: str
    source_sha256: str
    previous_review_sha256: str | None = None
    assertions: list[AssertionReview] = Field(min_length=1, max_length=64)


def install_review_api(app, catalog, directory):
    revisions = Lock()

    def latest(identity, assessment, source):
        saved = [entry for _, _, entry in catalog.exchange.reviews(assessment, source).get(identity, {}).values()]
        if not saved:
            return 0, None
        head = max(saved, key=lambda row: row.get("revision", 0))
        return head.get("revision", 0), sha256(canonical(head)).hexdigest()

    def inputs(assessment_id):
        try:
            snapshot, digest = catalog.review_inputs(assessment_id)
        except (KeyError, ValueError, OSError):
            raise HTTPException(404, "Completed assessment evidence is unavailable") from None
        if snapshot.get("invalid_sources"):
            raise HTTPException(409, "Resolve invalid source artifacts before review")
        records = [row for row in snapshot["records"] if "artifact_sha256" in row]
        if not records:
            raise HTTPException(409, "This assessment has no execution-captured records for review")
        return records, digest, snapshot["unreviewed_hypotheses"]

    @app.get("/reporting/review")
    def open_review(request: Request, assessment_id: str):
        identity = authenticate(request, assessment_id, {"reviewer"})["reviewer_id"]
        records, digest, candidates = inputs(assessment_id)
        try:
            _, head = latest(identity, assessment_id, digest)
        except (KeyError, ValueError, OSError, TypeError):
            raise HTTPException(409, "Review history failed integrity verification") from None
        return {"reviewer": identity, "source_sha256": digest, "records": records, "candidates": candidates,
                "review_head": head, "mechanics": {tid: MECHANICS[tid] for tid in candidates if tid in MECHANICS}}

    @app.post("/reporting/review")
    def submit_review(request: Request, submission: Submission):
        identity = authenticate(request, submission.assessment_id, {"reviewer"})["reviewer_id"]
        records, digest, candidates = inputs(submission.assessment_id)
        if submission.source_sha256 != digest:
            raise HTTPException(409, "Evidence revision changed")
        sources = {row["source_id"] for row in records}
        claims = [(row.source_id, row.technique, row.role) for row in submission.assertions]
        if (len(set(claims)) != len(claims)
                or any(src not in sources or tid not in candidates or tid == "Unmapped" for src, tid, _ in claims)):
            raise HTTPException(422, "Review assertions must reference unique in-scope sources and candidates")
        if any(row.occurrence is not None and (not row.occurrence.strip() or row.disposition == "supported")
               for row in submission.assertions):
            raise HTTPException(422, "An occurrence can scope only a contradicted or unresolved assertion")
        values = {"actor": {"adversary", "benign"}, "authorization": {"authorized", "unauthorized"},
                  "outcome": {"completed", "failed"}, "process_session": {"linked", "unlinked"}}
        if any(row.value is not None and row.value not in ({MECHANICS.get(row.technique)} if row.role == "mechanic"
                                                           else values[row.role]) for row in submission.assertions):
            raise HTTPException(422, "Evidence value is invalid for the selected role")
        with revisions:
            try:
                revision, head = latest(identity, submission.assessment_id, digest)
            except (KeyError, ValueError, OSError, TypeError):
                raise HTTPException(409, "Review history failed integrity verification") from None
            if submission.previous_review_sha256 != head:
                raise HTTPException(409, "Review head changed; reopen evidence before submitting")
            body = submission.model_dump(exclude={"assertions": {
                index: {"occurrence"} for index, row in enumerate(submission.assertions) if row.occurrence is None
            }})
            receipt = {**body, "reviewer": identity, "revision": revision + 1,
                       "created_at": datetime.now(timezone.utc).isoformat(),
                       "status": "submitted_awaiting_independent_admission"}
            raw = canonical(receipt)
            proof = sha256(raw).hexdigest()
            slot = sha256(canonical([identity, submission.assessment_id, digest, revision + 1])).hexdigest()
            directory.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=directory, delete=False) as pending:
                temporary = Path(pending.name)
                pending.write(raw)
            try:
                # Reserve the revision separately so process-level races fail closed.
                with (directory / f"{slot}.lock").open("xb"):
                    pass
                os.link(temporary, directory / f"{slot}-{proof}.json")
            except FileExistsError:
                raise HTTPException(409, "Review revision already reserved") from None
            finally:
                temporary.unlink(missing_ok=True)
        return {**receipt, "review_sha256": proof}

    @app.get("/reporting/custody/package")
    def export_package(request: Request, assessment_id: str):
        authenticate(request, assessment_id, {"reviewer", "custodian"})
        try:
            wrapped, _ = catalog.exchange.package(assessment_id)
            body = canonical({**wrapped, "head": catalog.exchange.head(assessment_id)})
        except (LookupError, ValueError, OSError, TypeError, ReceiptStoreError):
            raise HTTPException(409, "Evidence package failed verification") from None
        return Response(body, media_type="application/json", headers={
            "Content-Disposition": f'attachment; filename="review-{assessment_id}.json"',
            "Cache-Control": "no-store",
        })

    @app.post("/reporting/custody/receipt", status_code=201)
    def import_receipt(request: Request, receipt: Receipt, assessment_id: str | None = None):
        if assessment_id is not None and assessment_id != receipt.assessment_id:
            raise HTTPException(409, "Receipt does not belong to the selected assessment")
        identity = authenticate(request, receipt.assessment_id, {"custodian"})
        try:
            return catalog.exchange.accept(receipt, identity)
        except (LookupError, ValueError, OSError, TypeError, ReceiptStoreError) as error:
            raise HTTPException(409, str(error) if isinstance(error, ValueError) else "Custody verification failed") from None
