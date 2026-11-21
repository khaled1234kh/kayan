import json
from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.trustgate.client import TrustGateDecision
from console.backend.reporting_api import install_reporting_api
from console.backend.reporting_exchange import canonical
from console.backend.sign_reporting_receipt import build_receipt
from eval.attack_evidence_admission_v2 import VERSION
from eval.fixtures.ai.attack_admission_v2 import issue
from eval.fixtures.ai.attack_fact_registry_v1.demo import SCOPE, _assert, _event, _fixture, _record
from integration.trustgate_client import AuthorizationResult
from test_signed_reporting_exchange import CUSTODY, ID, REVIEW, TASK, export, setup


CASES = json.loads((Path(__file__).parents[1] / "eval/fixtures/archived_signed_attribution_v1.json").read_bytes())["cases"]
BY_ID = {case["id"]: case for case in CASES}
TECHNIQUE = "T1486"
MECHANIC = "availability_impact_encryption"


def signed_fixture(case, catalog):
    """Use inert captured values and test-only facts to exercise exact receipt binding."""
    manifest, payloads = _fixture(ID)
    manifest["schema_version"] = VERSION
    trace, reviews, source_roles = [], {}, {}
    number = 0

    def source(role, event_number):
        nonlocal number
        number += 1
        ref = f"tool-{number:032x}"
        agent = f"test-only-{role}"
        audit_id = f"{number:08x}-1111-2222-3333-444444444444"
        output = {"status_code": 200 + number}
        proof = catalog.source_store.record(
            engagement=ID, agent=agent, role=role, task=ref, tool="inert_fixture_observation",
            target="127.0.0.1", auth=AuthorizationResult(True, "ALLOW", "fixture", audit_entry_id=audit_id),
            result=output, dispatched=True,
        )
        event = {"engagement_id": ID, "agent_role": role, "agent_id": agent, "task_id": ref,
                 "tool_name": "inert_fixture_observation", "target": "127.0.0.1"}
        trace.extend([
            {**event, "kind": "authorization_decision", "decision": "ALLOW", "audit_entry_id": audit_id},
            {**event, "kind": "tool_result", "source_artifact_sha256": proof},
        ])
        source_roles[ref] = role
        if event_number is not None:
            _record(manifest, payloads, ref, canonical(output), f"fixture-source-{number}", f"E{event_number}.{number}")
            manifest["sources"][-1]["upstream"] = []
        return ref

    def review(ref, role, value, disposition="supported", occurrence=None):
        reviews[ref, role] = {
            "source_id": ref, "technique": TECHNIQUE, "role": role, "value": value,
            "disposition": disposition,
        }
        if occurrence is not None:
            reviews[ref, role]["occurrence"] = occurrence

    shared = source("recon_agent", 9) if case.get("shared_adverse") else None
    for index, item in enumerate(case["events"], 1):
        name = item["id"]
        scope = {**SCOPE, "session": f"test-session-{index}"}
        _event(manifest, name, scope, "2026-11-20T09:10:00Z")
        action = source("webapp_agent", index)
        actor = source("recon_agent", index)
        policy = source("network_agent", index)
        authorization = "authorized" if item.get("authorized") else "unauthorized"
        for role, value, ref in (
            ("mechanic", MECHANIC, action), ("outcome", "completed", action),
            ("actor", "adversary", actor), ("authorization", authorization, policy),
        ):
            references = (ref, shared) if role == "actor" and shared else (ref,)
            _assert(manifest, name, scope, role, value, *references,
                    action=MECHANIC if role == "authorization" else None)
            if item.get("omit") != role:
                adverse = item.get("adverse") == role
                review(ref, role, None if adverse else value, "unresolved" if adverse else "supported",
                       occurrence=name if adverse else None)
                if role == "actor" and shared:
                    review(shared, role, value)
        if item.get("adverse") == "other_role":
            review(actor, "authorization", "authorized", "contradicted", occurrence=name)
    if shared:
        review(shared, "outcome", None, "unresolved")
    if case.get("unbound_adverse"):
        review(source("network_agent", None), "actor", None, "unresolved")

    session = catalog.sessions.load(ID)
    session["transcript"] = trace
    catalog.sessions.save(session)
    return manifest, payloads, list(reviews.values()), source_roles


def catalogue_for(package, manifest, payloads):
    raw, authority = issue(manifest)
    catalogue = {
        "assessment_id": ID, "title": "Signed occurrence attribution fixture", "status": "completed",
        "snapshot": raw.decode("ascii"), "custody": asdict(authority),
        "operational_evidence_sha256": package["source_sha256"],
        "review_receipt_sha256": [row["sha256"] for row in package["reviews"]],
        "records": [{"id": key, "revision": rev, "text": raw.decode()} for (key, rev), raw in payloads.items()],
    }
    return json.loads(json.dumps(catalogue, default=sorted))


@pytest.mark.parametrize("case", CASES + [
    {**BY_ID["adverse_on_distinct_occurrence"], "id": f"unique_source_{mode}",
     "scope_override": scope, "allowed": [], "withheld": ["alpha", "beta"]}
    for mode, scope in (("unscoped", None), ("wrong_existing_occurrence", "alpha"), ("unknown_occurrence", "unknown"))
] + [
    {**BY_ID["shared_adverse_source"], "id": "shared_source_with_explicit_scope", "scope_override": "alpha"},
    {**BY_ID["unscoped_adverse_source"], "id": "unbound_source_with_explicit_scope", "scope_override": "alpha"},
], ids=lambda case: case["id"])
def test_signed_admission_keeps_exact_sources_and_localizes_adverse_reviews(tmp_path, setup, case):
    launch, key, people, provision, _ = setup
    people[0]["reviewer_id"] = "synthetic-reviewer"
    provision()
    catalog, reviews = launch()
    manifest, payloads, decisions, owners = signed_fixture(case, catalog)
    if "scope_override" in case:
        for row in decisions:
            if row["disposition"] != "supported":
                row.pop("occurrence", None)
                if case["scope_override"] is not None:
                    row["occurrence"] = case["scope_override"]
    evidence = reviews.get("/reporting/review", params={"assessment_id": ID}, headers=REVIEW).json()
    reported = reviews.post("/reporting/review", headers=REVIEW, json={
        "assessment_id": ID, "source_sha256": evidence["source_sha256"], "assertions": decisions,
    })
    assert reported.status_code == 200, reported.text
    assert catalog.load(ID)["findings"] == []
    package = export(reviews)
    assert package["package"]["reviews"][0]["review"]["assertions"] == decisions
    catalogue = catalogue_for(package["package"], manifest, payloads)
    verified = catalog.evaluate_package(*catalog.review_inputs(ID), catalogue)
    assert {row["occurrence"] for row in verified["findings"]} == {
        row["id"] for row in case["events"] if not row.get("authorized")
    }
    receipt = build_receipt(package, catalogue, "fixture-key", key).model_dump()
    accepted = reviews.post("/reporting/custody/receipt", headers=CUSTODY, json=receipt)
    assert accepted.status_code == 201, accepted.text

    class Gate:
        async def authorize(self, **arguments):
            assert arguments["action"] == "write_report"
            return TrustGateDecision("reporting_agent", "write_report", True, "ALLOW", "fixture", None, "test-audit")

        def close(self):
            pass

    restored, _ = launch()
    app = FastAPI()
    install_reporting_api(app, catalog=restored, output=tmp_path / "reports", make_gate=lambda _: Gate())
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 5555)) as client:
        saved = client.post("/reporting/archive/run", json={"mode": "local", "assessment_id": ID})
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["custody_test_only"] is True
        actual = (
            sorted(row["occurrence"] for row in body["findings"]),
            sorted(row.get("occurrence", "<unbound>") for row in body["withheld"]),
        )
        assert actual == (case["allowed"], case["withheld"]), f"{case['id']}: {actual}"
        for row in body["withheld"]:
            if row["occurrence"] not in {claim.get("occurrence") for claim in verified["withheld"]}:
                assert row["reasons"] == ["independent_review_incomplete_or_adverse"]
        for finding in body["findings"]:
            assert {binding["role"]: owners[binding["record_id"]] for binding in finding["review_bindings"]} == {
                "mechanic": "webapp_agent", "outcome": "webapp_agent",
                "actor": "recon_agent", "authorization": "network_agent",
            }
            exact = {ref for row in manifest["assertions"] if row["event"]["id"] == finding["occurrence"]
                     for ref in row["statements"]}
            assert {binding["record_id"] for binding in finding["review_bindings"]} == exact
        assert client.get("/reporting/archive/result", params={
            "assessment_id": ID, "download": True,
        }).content == saved.content


@pytest.mark.parametrize(("scope", "disposition"), [
    (" ", "contradicted"), (["alpha"], "unresolved"), ("alpha", "supported"),
])
def test_invalid_occurrence_scope_cannot_create_a_review(setup, scope, disposition):
    launch, _, _, _, _ = setup
    _, client = launch()
    evidence = client.get("/reporting/review", params={"assessment_id": ID}, headers=REVIEW).json()
    submitted = client.post("/reporting/review", headers=REVIEW, json={
        "assessment_id": ID, "source_sha256": evidence["source_sha256"], "assertions": [
            {"source_id": TASK, "technique": TECHNIQUE, "role": "actor", "disposition": disposition,
             "value": "adversary", "occurrence": scope},
        ],
    })
    assert submitted.status_code == 422
    assert export(client)["package"]["reviews"] == []
