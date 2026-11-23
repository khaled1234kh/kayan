import json

from eval import cloud_automatic_proof_v1 as base
from eval.cloud_real_comparison_prep import prepare, verified_inputs


def test_pinned_offline_bundle_keeps_arms_matched_and_results_separate():
    from tests.private_artifacts import require_private
    require_private('.build/cloud-automatic-proof-v1.jsonl')
    plan = verified_inputs()
    bundle = prepare(plan)
    assert bundle["cloud_status"] == "blocked"
    assert all(value is None for value in plan["authorizations"].values())
    for case, row in bundle["cases"].items():
        _, _, evidence = base.fixture(case)
        drafts = row["cloud_drafts"]
        contents = {arm: json.loads(body["messages"][1]["content"]) for arm, body in drafts.items()}
        assert contents["B"] == contents["D"]
        assert contents["C"] == {**contents["B"], "references": row["lexical_references"]}
        assert contents["B"]["observations"] == evidence
        assert set(contents["B"]) == {"observations", "hypotheses"}
        assert all(item["max_output_tokens"] == row["local_request"]["options"]["num_predict"]
                   for item in drafts.values())
        assert row["cloud_results"] is None
        assert row["local_result_replay"]["verdict"]["review_items"] == []
    assert sum(len(row["authored_control"]["review_items"]) for row in bundle["cases"].values()) == 3
