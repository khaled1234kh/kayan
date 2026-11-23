"""Mock-only workflow tests. No frozen confirmation observations enter the model."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from ai.mitre.stix import MitreTechnique
from eval import ai_confirmation_inputs as inputs
from eval import ai_mapping_confirmation as runner
from eval.ai_confirmation_review import RUBRIC, AdjudicatedCase
from eval.ai_confirmation_scoring import compare, score_case
from eval.ai_mapping_review import prepare, save

RECORDS = {"E1": "The first corroborated mock record.", "E2": "The second corroborated mock record.",
           "E3": "A third mock record can independently corroborate the full action.", "E4": "An unrelated mock record."}
TECHNIQUE = MitreTechnique("T1234", "Mock", "Example classification", (), "", (), "")
ACTIVE = {TECHNIQUE.technique_id}


def label(groups=None, cid="mock-positive", disposition="confirmed_adversary", resolution="score"):
    return AdjudicatedCase(id=cid, disposition=disposition, resolution=resolution,
                           evidence_sets={"T1234": groups} if groups else {},
                           rationale="Synthetic scoring fixture only")


def response(*records):
    return json.dumps({"mappings": [{"technique_id": "T1234", "record_id": rid,
                                      "quote": RECORDS[rid], "justification": "Only a synthetic test."} for rid in records]})


def mock_rule():
    return SimpleNamespace(unsupported_pair_weight=2, missed_pair_weight=1, min_weighted_improvement_per_case=.1,
                           max_negative_specificity_loss=0, interval_requirement="above_zero")


def mock_returns(root, monkeypatch):
    files, packet_metadata = {}, {}
    for name in ("diagnostic", "confirmation"):
        packet = root / f"{name}-mock-observations.json"
        folder = root / name
        folder.mkdir()
        save(packet, {"cases": [{"id": f"{name}-mock-pos", "records": RECORDS},
                                {"id": f"{name}-mock-neg", "records": RECORDS}]})
        files[name] = packet
        packet_metadata[name] = {"sha256": inputs.sha(packet), "forms": {}}
        metadata = []
        for slot in ("A", "B"):
            form_path = folder / f"blank-{slot}.json"
            save(form_path, prepare(packet, slot))
            form_hash = inputs.sha(form_path)
            packet_metadata[name]["forms"][slot] = form_hash
            returned = folder / f"reviewer-{slot.lower()}.json"
            form = json.loads(form_path.read_bytes())
            for row in form["cases"]:
                positive = row["id"].endswith("-pos")
                row.update(disposition="confirmed_adversary" if positive else "authorized", ambiguous=False,
                           mappings={"T1234": ["E1", "E2"] if slot == "A" else ["E3"]} if positive else {},
                           observed_action="Synthetic mock only", evidence_reliability="Synthetic mock only",
                           contradictions="Synthetic mock only", rationale="Synthetic mock only")
            save(returned, form)
            metadata.append({"slot": slot, "identity": f"MOCK reviewer {slot}", "qualification": "MOCK qualification",
                             "completed_on": "2026-11-19", "returned_sha256": inputs.sha(returned),
                             "issued_form_sha256": form_hash,
                             "independently_reviewed_without_labels_or_model_outputs": True})
        save(folder / "receipt.json", {"packet_sha256": inputs.sha(packet), "taxonomy_sha256": inputs.TAXONOMY_HASH,
                                      "coordinator": "MOCK only", "originals_and_independence_verified": True,
                                      "reviewers": metadata})
    monkeypatch.setattr(inputs, "PACKETS", files)
    adjudications = {}
    for name in files:
        folder = root / name
        report, blinded, _, _ = inputs.read_reviews(folder, name, packet_metadata[name], ACTIVE)
        assert report["metrics"]["any_mapping"]["agreement"] == 1
        assert report["metrics"]["any_mapping"]["cohens_kappa"] == 1
        assert report["metrics"]["exact_technique_record_pairs"]["agreement"] == .5
        assert report["metrics"]["exact_technique_record_pairs"]["cohens_kappa"] is None
        assert len(report["requires_adjudication"]) == 1
        save(folder / "agreement.json", report)
        draft = inputs.draft_adjudication(blinded, inputs.sha(folder / "agreement.json"))
        assert all(row["evidence_sets"] is None and row["rationale"] is None for row in draft["cases"])
        resolved = [label([["E1", "E2"], ["E3"]], f"{name}-mock-pos"),
                    label(cid=f"{name}-mock-neg", disposition="authorized")]
        save(folder / "adjudication.json", {"rubric": RUBRIC, "label_version": "mock-v1",
                                          "packet_sha256": packet_metadata[name]["sha256"], "adjudicator": "MOCK only",
                                          "adjudicated_on": "2026-11-20", "agreement_sha256": inputs.sha(folder / "agreement.json"),
                                          "cases": [row.model_dump() for row in resolved]})
        adjudications[name] = inputs.sha(folder / "adjudication.json")
    approval_path = root / "approval.json"
    save(approval_path, {"rubric": RUBRIC, "comparison": inputs.COMPARISON, "stakeholder": "MOCK only",
                         "approved_on": "2026-11-20", "adjudications_sha256": adjudications,
                         "protocol_sha256": "a"*64, "rationale": "Mock only for tests",
                         **vars(mock_rule())})
    return packet_metadata, approval_path


@pytest.mark.parametrize(("submitted", "counts", "exact"), [
    (["E1", "E2"], (2, 0, 0), True),
    (["E3"], (1, 0, 0), True),
    (["E1"], (0, 1, 2), False),
    (["E1", "E2", "E3"], (2, 0, 0), True),
    (["E1", "E3"], (1, 1, 0), False),
    (["E1", "E2", "E4"], (2, 1, 0), False),
    ([], (0, 0, 1), False),
])
def test_joint_and_alternative_evidence(submitted, counts, exact):
    result = score_case(label([["E1", "E2"], ["E3"]]), RECORDS, response(*submitted), ACTIVE)
    assert tuple(len(result[key]) for key in ("tp", "fp", "fn")) == counts
    assert result["exact"] is exact


def test_reference_only_and_malformed_citations_cannot_earn_credit():
    bad = response("E1").replace(RECORDS["E1"], "Quote found only in reference")
    result = score_case(label([["E1"]]), RECORDS, bad, ACTIVE)
    assert result["binding_blocks"] == [("T1234", "E1", "quote_mismatch")]
    assert len(result["fp"]) == len(result["fn"]) == 1
    negative = label(disposition="unconfirmed")
    assert score_case(negative, RECORDS, response(), ACTIVE)["exact"]
    assert not score_case(negative, RECORDS, "invalid", ACTIVE)["abstained"]
    assert not score_case(label(resolution="exclude_ambiguous"), RECORDS, response(), ACTIVE)["scored"]


def test_mock_adjudication_fails_closed_on_missing_approval_or_changed_original(tmp_path, monkeypatch):
    metadata, approval = mock_returns(tmp_path, monkeypatch)
    cases, decision, proof = inputs.read_inputs(tmp_path, metadata, [TECHNIQUE], "a" * 64)
    assert cases["confirmation-mock-pos"].evidence_sets == {"T1234": [["E1", "E2"], ["E3"]]}
    assert proof["approval_sha256"] == inputs.sha(approval)
    assert decision.unsupported_pair_weight == 2
    with pytest.raises(ValueError, match="approval does not bind"):
        inputs.read_inputs(tmp_path, metadata, [TECHNIQUE], "b" * 64)
    approval.unlink()
    with pytest.raises(FileNotFoundError, match="approval.json"):
        inputs.read_inputs(tmp_path, metadata, [TECHNIQUE], "a" * 64)
    returned = tmp_path / "confirmation/reviewer-a.json"
    returned.write_bytes(returned.read_bytes() + b" ")
    with pytest.raises(ValueError, match="mismatched original"):
        inputs.read_inputs(tmp_path, metadata, [TECHNIQUE], "a" * 64)


def test_adjudication_rejects_nonminimal_groups(tmp_path, monkeypatch):
    metadata, _ = mock_returns(tmp_path, monkeypatch)
    path = tmp_path / "diagnostic/adjudication.json"
    document = json.loads(path.read_bytes())
    document["cases"][0]["evidence_sets"]["T1234"] = [["E1", "E2"], ["E1"]]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="distinct, minimal and grounded"):
        inputs.read_inputs(tmp_path, metadata, [TECHNIQUE], "a" * 64)


def test_run_checks_human_gate_before_transport(tmp_path, monkeypatch):
    protocol = tmp_path / "protocol.json"
    save(protocol, {"ollama_version": "mock"})
    monkeypatch.setattr(runner, "PROTOCOL", protocol)
    monkeypatch.setattr(runner, "audit_packets", lambda: ({}, [], {}))
    monkeypatch.setattr(runner, "catalogue", lambda: (None, []))
    monkeypatch.setattr(runner, "protocol_basis", lambda *_: {"ollama_version": "mock"})

    def blocked(*_):
        raise FileNotFoundError("Missing independent human reviews")

    def unexpected(*_):
        pytest.fail("Contacted a route or model before the human gate")

    monkeypatch.setattr(runner, "read_inputs", blocked)
    monkeypatch.setattr(runner, "console_state", unexpected)
    monkeypatch.setattr(httpx, "AsyncClient", unexpected)
    with pytest.raises(FileNotFoundError, match="human reviews"):
        asyncio.run(runner.run(tmp_path))


def test_mock_paired_ledger_retains_failed_and_malformed_once(tmp_path):
    cases = [{"id": cid, "family": family, "records": RECORDS}
             for cid, family in [("mock-b", "F1"), ("mock-d", "F2"), ("mock-a", "F1"), ("mock-c", "F2")]]
    labels = {c["id"]: label([["E1"]], c["id"]) if i % 2 == 0 else label(cid=c["id"], disposition="authorized")
              for i, c in enumerate(cases)}
    lookup = {TECHNIQUE.technique_id: TECHNIQUE}
    visited = []

    def transport(request):
        visited.append(request)
        if len(visited) == 1:
            return httpx.Response(503, text="mock server failure")
        data = {"done": True, "done_reason": "stop", "model": runner.MODEL, "message": {"content": response()}}
        if len(visited) == 2:
            data["message"]["content"] = "malformed JSON"
        return httpx.Response(200, json=data)

    async def scenario():
        async with httpx.AsyncClient(base_url=runner.SERVER, transport=httpx.MockTransport(transport)) as client:
            with (tmp_path / "mock-attempts.jsonl").open("x") as log:
                return await runner.collect(cases, labels, SimpleNamespace(sha256="mock"), lookup,
                                            lambda *_: ([("T1234", 1)], .5),
                                            lambda request: runner.send_once(client, request), log)

    rows = asyncio.run(scenario())
    ledger = [json.loads(line) for line in (tmp_path / "mock-attempts.jsonl").read_text().splitlines()]
    assert len(visited) == 8 and len(ledger) == 16
    assert [row["arm"] for row in ledger if row["event"] == "start"] == [*runner.ARMS, *runner.ARMS, *reversed(runner.ARMS), *reversed(runner.ARMS)]
    assert ledger[1]["execution_error"] == "HTTP 503" and ledger[1]["raw_body_base64"] and ledger[1]["transport_error"]
    assert ledger[3]["content"] == "malformed JSON" and not ledger[3]["contract"] and not ledger[3]["transport_error"]
    outcome = compare(*(rows[arm] for arm in runner.ARMS), mock_rule(), draws=100)
    assert not outcome["both_arms_contract_complete"] and not outcome["research_rule_met"]
    result = tmp_path / "mock-run"
    runner.reserve(result)
    with pytest.raises(FileExistsError):
        runner.reserve(result)
