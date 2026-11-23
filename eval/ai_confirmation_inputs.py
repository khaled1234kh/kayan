"""Verify the frozen study inputs and bind human-reviewed labels to the run."""

import json
from importlib.metadata import version

from ai.config import load_config
from ai.mitre.ranking import E5_REVISION
from ai.mitre.stix import load_techniques
from eval.ai_confirmation_review import (
    RUBRIC, Adjudication, Approval, ReviewReceipt, compare_reviews, metadata_date, resolve_receipt,
    validate_adjudication,
)
from eval.ai_mapping_review import prepare, save
from eval.ai_retrieval_mapping import MODEL, ROOT, SYSTEM, Prediction, digest

HISTORY = ROOT / "eval/reports/ai_mapping_ablation_20261120"
PACKETS = {
    "diagnostic": ROOT / "eval/reports/ai_retrieval_mapping_20261120/blinded_review_packet.json",
    "confirmation": ROOT / "eval/fixtures/ai/evidence_mapping_confirmation_v1_unlabelled.json",
}
FRESH_HASH = "9451fde497ce8fa228f0eb0a7de2e836f514e6e5a8c165771637691d1f35d50c"
HISTORICAL_MANIFEST_HASH = "05bdaa1e466b6b3adc80a351595fa732e8bf7fe51158f88bdc86bc796263a4a8"
HISTORICAL_LOCK_HASH = "1a63f7429ed6f8c022e97d4f3282efc56ee40884ca00192aa4ca216129714e5b"
TAXONOMY_HASH = "539a843a7b53ed9749740b2123dddae3726b1a4831841c32aca740b011b910b5"
MODEL_HASH = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
COMPARISON = "attack-confirmation-v1"
OPTIONS = {"num_ctx": 4096, "num_predict": 370, "temperature": 0}
E5_CAP = 192
K = 5
ARMS = ("bm25_k5", "hybrid192_k5")
POLICY = "One attempt per case/arm, no retries or replay. Retain failed attempts and stop on interruption."
PRIVATE = ROOT / ".build/attack_confirmation"
PROTOCOL = ROOT / "eval/reports/ai_mapping_confirmation_preparation_20261120/protocol.json"
SOURCE_PATHS = (
    "eval/ai_confirmation_inputs.py", "eval/ai_confirmation_review.py", "eval/ai_confirmation_scoring.py",
    "eval/ai_mapping_confirmation.py", "eval/ai_mapping_review.py", "eval/ai_retrieval_mapping.py",
    "eval/ai_mapping_ablation.py", "ai/mitre/ranking.py", "ai/mitre/stix.py", "ai/config.py",
)


def sha(path):
    return digest(path.read_bytes())


def checked_json(path, expected):
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError(f"Frozen hash mismatch for {path.name}")
    return json.loads(raw)


def audit_packets():
    manifest = checked_json(HISTORY / "manifest.json", HISTORICAL_MANIFEST_HASH)
    old_lock = checked_json(HISTORY / "review/confirmation-lock.json", HISTORICAL_LOCK_HASH)
    fresh = checked_json(PACKETS["confirmation"], FRESH_HASH)["cases"]
    families = {case["family"] for case in fresh}
    if (len(fresh) != 24 or len(families) != 12 or len({case["id"] for case in fresh}) != 24
            or any(set(case) != {"id", "family", "records"} for case in fresh)
            or any(sum(case["family"] == family for case in fresh) != 2 for family in families)):
        raise ValueError("Frozen cohort must have 24 observation-only cases in 12 pairs")
    if (old_lock["fixture_sha256"] != FRESH_HASH or old_lock["manifest_sha256"] != HISTORICAL_MANIFEST_HASH
            or (old_lock["baseline"], old_lock["challenger"]) != ARMS or manifest["bundle_sha256"] != TAXONOMY_HASH
            or manifest["model_digest"] != MODEL_HASH or manifest["model"] != MODEL
            or manifest["e5_revision"] != E5_REVISION or manifest["schema"] != Prediction.model_json_schema()
            or any(old_lock["arm_parameters_from_manifest"][arm] != manifest["arms"][arm]
                   or manifest["arms"][arm]["system"] != SYSTEM or manifest["arms"][arm]["k"] != K for arm in ARMS)):
        raise ValueError("Historical confirmation settings do not match the preregistered comparison")
    checks = {}
    for line in (HISTORY / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if sha(HISTORY / name) != expected:
            raise ValueError(f"Historical checksum mismatch for {name}")
        checks[name] = expected
    if len(checks) != 22:
        raise ValueError("Historical artifact checksum list is incomplete")
    originals = json.loads((HISTORY / "verification.json").read_bytes())["blinded_forms_sha256"]
    packets = {}
    for cohort, path in PACKETS.items():
        hashes = {}
        for slot in ("A", "B"):
            name = f"review/{cohort}-reviewer-{slot.lower()}.json"
            actual = checked_json(HISTORY / name, originals[name])
            blank = json.loads(json.dumps(prepare(path, slot)))
            if actual != blank or len(blank["cases"]) != (32 if cohort == "diagnostic" else 24):
                raise ValueError(f"Unexpected fields or altered observations in {name}")
            hashes[slot] = originals[name]
        packets[cohort] = {"sha256": sha(path), "forms": hashes, "cases": len(blank["cases"])}
    return manifest, fresh, packets


def protocol_basis(manifest, packets, snapshot, ollama_version):
    files = {path.name: sha(path) for path in sorted(snapshot.iterdir()) if path.is_file()}
    if snapshot.name != E5_REVISION or files != manifest["e5_file_hashes"]:
        raise ValueError("Local E5 snapshot is missing or changed")
    return {
        "comparison": COMPARISON, "rubric": RUBRIC,
        "packets": packets, "historical_manifest_sha256": HISTORICAL_MANIFEST_HASH,
        "taxonomy_sha256": TAXONOMY_HASH, "taxonomy_version": "20.1",
        "model": MODEL, "model_sha256": MODEL_HASH, "options": OPTIONS, "ollama_version": ollama_version,
        "e5_revision": E5_REVISION, "e5_file_hashes": files, "e5_token_cap": E5_CAP,
        "schema": manifest["schema"], "arms": {arm: manifest["arms"][arm] for arm in ARMS},
        "reference_format": "Historical provenance fields and first 400 description characters",
        "request_order": "Sorted families then sorted case IDs, reverse arm order on alternating families",
        "attempt_policy": POLICY, "logging": "Private one-shot attempt ledger with raw responses and score trace",
        "software_versions": {name: version(name) for name in ("torch", "transformers", "scikit-learn", "pydantic", "httpx", "psutil")},
        "source_sha256": {name: sha(ROOT / name) for name in SOURCE_PATHS},
    }


def read_reviews(directory, cohort, packet_metadata, active_ids):
    returned = {slot: (directory / f"reviewer-{slot.lower()}.json").read_bytes() for slot in ("A", "B")}
    returned_hashes = {slot: digest(raw) for slot, raw in returned.items()}
    receipt_path = directory / "receipt.json"
    raw_receipt = receipt_path.read_bytes()
    receipt = ReviewReceipt.model_validate_json(raw_receipt)
    reviewers = resolve_receipt(receipt, packet_metadata["sha256"], TAXONOMY_HASH,
                                returned_hashes, packet_metadata["forms"])
    sheets = {slot: json.loads(raw) for slot, raw in returned.items()}
    if any(sheets[slot]["reviewer_id"] != slot for slot in sheets):
        raise ValueError("The returned form must retain the original A/B slot")
    packet = prepare(PACKETS[cohort], "")
    result = compare_reviews(sheets["A"], sheets["B"], packet, active_ids)
    result["review_receipt_sha256"] = digest(raw_receipt)
    result["originals_sha256"] = returned_hashes
    return result, packet, reviewers, sheets


def read_inputs(directory, packet_metadata, techniques, protocol_hash):
    active_ids = {technique.technique_id for technique in techniques}
    hashes, metadata, identities, adjudicated = {}, {}, {}, {}
    for cohort in PACKETS:
        folder = directory / cohort
        agreement, packet, reviewers, sheets = read_reviews(folder, cohort, packet_metadata[cohort], active_ids)
        agreement_path = folder / "agreement.json"
        agreement_raw = agreement_path.read_bytes()
        if json.loads(agreement_raw) != agreement:
            raise ValueError(f"Stored agreement differs from the returned originals in {cohort}")
        label_path = folder / "adjudication.json"
        label_raw = label_path.read_bytes()
        labels = Adjudication.model_validate_json(label_raw)
        adjudicated[cohort] = validate_adjudication(
            labels, {case["id"]: case["records"] for case in packet["cases"]}, active_ids,
            packet_hash=packet["packet_sha256"], agreement_hash=digest(agreement_raw),
            after_date=max(metadata_date(item.completed_on) for item in reviewers.values()),
        )
        metadata[cohort] = {"version": labels.label_version, "date": labels.adjudicated_on,
                            "agreement_sha256": digest(agreement_raw), "originals": agreement["originals_sha256"],
                            "receipt_sha256": agreement["review_receipt_sha256"]}
        identities[cohort] = {slot: record.identity.casefold() for slot, record in reviewers.items()}
        hashes[cohort] = digest(label_raw)
    if identities["diagnostic"] != identities["confirmation"]:
        raise ValueError("The two cohorts must be reviewed by the same reviewer in each slot")
    approval_raw = (directory / "approval.json").read_bytes()
    approval = Approval.model_validate_json(approval_raw)
    if (approval.rubric != RUBRIC or approval.comparison != COMPARISON or approval.protocol_sha256 != protocol_hash
            or approval.adjudications_sha256 != hashes or approval.interval_requirement not in {"above_zero", "meets_margin"}
            or metadata_date(approval.approved_on) < max(metadata_date(row["date"]) for row in metadata.values())):
        raise ValueError("Stakeholder approval does not bind both adjudications and this protocol")
    labels = adjudicated["confirmation"]
    if {bool(row.evidence_sets) for row in labels.values() if row.resolution == "score"} != {True, False}:
        raise ValueError("The confirmation requires both scored positive and scored negative cases")
    return labels, approval, {"adjudications": hashes, "review_metadata": metadata, "approval_sha256": digest(approval_raw)}


def catalogue():
    config = load_config(load_env=False).mitre
    if (config.version, config.sha256) != ("20.1", TAXONOMY_HASH):
        raise ValueError("Unexpected ATT&CK version or content digest")
    return config, load_techniques(config)


def write_agreement(directory, cohort, output):
    _, _, packets = audit_packets()
    _, techniques = catalogue()
    result, _, _, _ = read_reviews(directory / cohort, cohort, packets[cohort], {t.technique_id for t in techniques})
    save(output, result)


def draft_adjudication(packet, agreement_hash):
    return {"rubric": RUBRIC, "packet_sha256": packet["packet_sha256"], "agreement_sha256": agreement_hash,
            "label_version": None, "adjudicator": None, "adjudicated_on": None, "cases": [
                {"id": case["id"], "disposition": None, "resolution": None, "evidence_sets": None, "rationale": None}
                for case in packet["cases"]
            ]}


def write_adjudication_draft(directory, cohort):
    _, _, packets = audit_packets()
    _, techniques = catalogue()
    folder = directory / cohort
    report, packet, _, _ = read_reviews(folder, cohort, packets[cohort], {t.technique_id for t in techniques})
    raw = (folder / "agreement.json").read_bytes()
    if json.loads(raw) != report:
        raise ValueError("Stored agreement differs from the returned originals")
    save(folder / "adjudication-draft.json", draft_adjudication(packet, digest(raw)))
