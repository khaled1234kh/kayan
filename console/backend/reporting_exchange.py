"""Canonical evidence packages and externally signed, append-only custody receipts."""

from base64 import b64decode
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from pydantic import BaseModel, ConfigDict, Field

from console.backend.reporting_identity import ROOT, enrolment

PACKAGE_VERSION = "kayan.review-package/1"
RECEIPT_VERSION = "kayan.custody-receipt/1"


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(value):
    return sha256(value).hexdigest()


class Receipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assessment_id: str
    key_id: str
    package_sha256: str
    sequence: int = Field(ge=1, le=1_000_000)
    previous_receipt_sha256: str | None
    catalogue: dict
    signature: str = Field(max_length=128)

    def signed_bytes(self):
        return canonical({"version": RECEIPT_VERSION, **self.model_dump(exclude={"signature"})})


class SignedExchange:
    def __init__(self, catalog, directory):
        self.catalog = catalog
        self.directory = directory
        self.database = directory.parent / "signed-custody.sqlite3"

    def _connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.database, timeout=5)
        db.execute("""CREATE TABLE IF NOT EXISTS receipts
            (assessment TEXT, sequence INTEGER, digest TEXT UNIQUE, body BLOB,
             PRIMARY KEY (assessment, sequence))""")
        return db

    def reviews(self, assessment_id, source_sha256, people=None):
        active, chains = {}, {}
        for path in self.directory.glob("*.json"):
            raw = path.read_bytes()
            review = json.loads(raw)
            if review["assessment_id"] != assessment_id or review["source_sha256"] != source_sha256:
                continue
            proof = digest(raw)
            if not path.stem.endswith(f"-{proof}"):
                raise ValueError("Review receipt integrity check failed")
            reviewer = review["reviewer"]
            if people is not None:
                person = people.get(reviewer.casefold(), {})
                if (person.get("role") != "reviewer" or not person.get("active")
                        or assessment_id not in person["assessment_ids"]):
                    raise ValueError("A current review comes from an inactive or unassigned reviewer")
            if not isinstance(review.get("revision", 0), int):
                raise ValueError("Review revision is invalid")
            chain = chains.setdefault(reviewer, {})
            revision = review.get("revision", 0)
            if revision > 0 and revision in chain:
                raise ValueError("Duplicate immutable review revision")
            if revision > 0 or 0 not in chain:
                chain[revision] = (proof, review.get("previous_review_sha256"))
            group = active.setdefault(reviewer, {})
            for assertion in review["assertions"]:
                key = (assertion["source_id"], assertion["technique"], assertion["role"])
                previous = group.get(key)
                revision = review.get("revision", 0)
                if previous and previous[0] == revision:
                    raise ValueError("Conflicting review revisions")
                if previous is None or previous[0] < revision:
                    group[key] = (revision, proof, review)
        for chain in chains.values():
            head = chain.get(0, (None, None))[0]
            for index, revision in enumerate(sorted(number for number in chain if number > 0), 1):
                proof, parent = chain[revision]
                if revision != index or parent != head:
                    raise ValueError("Review revision chain is incomplete")
                head = proof
        return active

    def package(self, assessment_id):
        return self._package(assessment_id, self.catalog.review_inputs(assessment_id), enrolment())

    def _package(self, assessment_id, evidence, people):
        snapshot, source_sha256 = evidence
        captures = [row for row in snapshot["records"] if "artifact_sha256" in row]
        if snapshot.get("invalid_sources") or not captures:
            raise ValueError("No intact execution evidence is available for exchange")
        active = self.reviews(assessment_id, source_sha256, people)
        reviews = {proof: review for group in active.values() for _, proof, review in group.values()}
        # Export only execution captures. Historical transcript output may include private data.
        payload = {"version": PACKAGE_VERSION, "assessment_id": assessment_id, "source_sha256": source_sha256,
                   "sources": captures, "candidates": snapshot["unreviewed_hypotheses"],
                   "reviews": [{"sha256": proof, "review": review} for proof, review in sorted(reviews.items())]}
        return {"package_sha256": digest(canonical(payload)), "package": payload}, active

    @staticmethod
    def _head(db, assessment_id):
        return db.execute("SELECT sequence, digest, body FROM receipts WHERE assessment=? ORDER BY sequence DESC LIMIT 1",
                          (assessment_id,)).fetchone()

    def head(self, assessment_id):
        if not self.database.is_file():
            return None
        with self._connect() as db:
            row = self._head(db, assessment_id)
        return {"sequence": row[0], "receipt_sha256": row[1]} if row else None

    def _evaluate(self, receipt, evidence=None):
        people = enrolment()
        signer = next((row for row in people.values() if row.get("key_id") == receipt.key_id), None)
        if (not signer or signer["role"] != "custodian" or not signer["active"]
                or receipt.assessment_id not in signer["assessment_ids"]):
            raise ValueError("Custodian key is revoked or untrusted for this assessment")
        path = Path(signer["public_key_file"]).resolve(strict=True)
        if path.is_relative_to(ROOT):
            raise ValueError("Custodian key is managed outside the checkout")
        pem = path.read_bytes()
        key = load_pem_public_key(pem)
        if digest(pem) != signer["public_key_sha256"] or not isinstance(key, Ed25519PublicKey):
            raise ValueError("Configured custodian public key is invalid")
        try:
            key.verify(b64decode(receipt.signature, validate=True), receipt.signed_bytes())
        except (InvalidSignature, ValueError) as exc:
            raise ValueError("Custody receipt signature is invalid") from exc

        if evidence is None:
            evidence = self.catalog.review_inputs(receipt.assessment_id)
        package, active = self._package(receipt.assessment_id, evidence, people)
        if receipt.package_sha256 != package["package_sha256"] or not active:
            raise ValueError("Custody receipt does not match current evidence and reviews")
        if signer["reviewer_id"].casefold() in {person.casefold() for person in active}:
            raise ValueError("Reviewer and custodian must be different people")
        if any(people[person.casefold()]["test_only"] != signer["test_only"] for person in active):
            raise ValueError("Test-only identities cannot be mixed with operational reviewers or custodians")
        dispositions, approved_sources = {}, set()
        for reviewer, group in active.items():
            for assertion_key, (_, _, review) in group.items():
                row = next(row for row in review["assertions"]
                           if (row["source_id"], row["technique"], row["role"]) == assertion_key)
                dispositions.setdefault(assertion_key, set()).add(
                    (row["disposition"], row.get("value"), row.get("occurrence")))
                if row["disposition"] == "supported" and row.get("value"):
                    approved_sources.add((*assertion_key, row["value"], reviewer))
        if any(len(values) > 1 for values in dispositions.values()):
            raise ValueError("Reviewers disagree on at least one current assertion")

        snapshot, source_sha256 = evidence
        review_hashes = {row["sha256"] for row in package["package"]["reviews"]}
        if set(receipt.catalogue.get("review_receipt_sha256", ())) != review_hashes:
            raise ValueError("Catalogue does not bind the active reviewer decisions")
        report = self.catalog.evaluate_package(snapshot, source_sha256, receipt.catalogue)
        kept, held = [], list(report["withheld"])
        occurrence_counts = Counter((row["technique"], row.get("occurrence"))
                                    for row in [*report["findings"], *held])
        technique_counts = Counter(row["technique"] for row in [*report["findings"], *held])
        occurrences_by_source = defaultdict(set)
        for finding in report["findings"]:
            for item in finding["review_bindings"]:
                occurrences_by_source[finding["technique"], item["record_id"]].add(finding["occurrence"])

        blocked = set()
        for (source, tid, _), values in dispositions.items():
            for mark, _, occurrence in values:
                if mark == "supported":
                    continue
                # Scope is signed with the review. An exact, unique verifier binding must corroborate it.
                if (occurrence is not None and occurrence_counts[tid, occurrence] == 1
                        and occurrences_by_source[tid, source] == {occurrence}):
                    blocked.add((tid, occurrence))
                else:
                    blocked.add((tid, None))
        for finding in report["findings"]:
            tid = finding["technique"]
            occurrence = finding["occurrence"]
            # The admission adapter exposes each actual record ID and its reviewed role.
            needed = {(item["record_id"], tid, item["role"], item["value"], item["reviewer"])
                      for item in finding["review_bindings"]}
            if (tid, None) in blocked or (tid, occurrence) in blocked or not needed or not needed <= approved_sources:
                claim = {"technique": tid, "reasons": ["independent_review_incomplete_or_adverse"]}
                if technique_counts[tid] > 1:
                    claim["occurrence"] = occurrence
                held.append(claim)
            else:
                kept.append(finding)
        return {**report, "findings": kept, "withheld": held,
                "review_status": "verified", "admission_status": "evaluated",
                "custody_test_only": signer["test_only"]}

    def accept(self, receipt, identity):
        if identity.get("key_id") != receipt.key_id:
            raise ValueError("Importing custodian does not own the signing key")
        report = self._evaluate(receipt)
        body = canonical(receipt.model_dump())
        proof = digest(body)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = self._head(db, receipt.assessment_id)
            if (receipt.sequence != (previous[0] + 1 if previous else 1)
                    or receipt.previous_receipt_sha256 != (previous[1] if previous else None)):
                raise ValueError("Receipt replay or invalid predecessor")
            _, current_source = self.catalog.review_inputs(receipt.assessment_id)
            if current_source != report["source_sha256"]:
                raise ValueError("Evidence changed during custody import")
            db.execute("INSERT INTO receipts VALUES (?, ?, ?, ?)",
                       (receipt.assessment_id, receipt.sequence, proof, body))
        return {"receipt_sha256": proof, "sequence": receipt.sequence, "admission_status": report["admission_status"]}

    def evaluate_current(self, assessment_id, evidence):
        if not self.database.is_file():
            return None
        with self._connect() as db:
            row = self._head(db, assessment_id)
            if row is None:
                return None
            sequence, proof, raw = row
            previous = db.execute("SELECT digest FROM receipts WHERE assessment=? AND sequence=?",
                                  (assessment_id, sequence - 1)).fetchone()
        receipt = Receipt.model_validate_json(raw)
        if (digest(raw) != proof or receipt.assessment_id != assessment_id or receipt.sequence != sequence
                or (sequence > 1 and previous is None)
                or receipt.previous_receipt_sha256 != (previous[0] if previous else None)):
            raise ValueError("Stored receipt integrity or continuity check failed")
        return {**self._evaluate(receipt, evidence), "report_revision": proof, "custody_receipt_sha256": proof}

