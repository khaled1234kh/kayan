from eval.attack_experiment_v2 import read
from eval.cloud_track_a import LOCK, assemble_reviewed_groups, proof_experiment


def test_proof_assembly_does_not_invent_hypotheses_or_discard_bad_citations():
    groups = {"T1486": ["E1.1", "E2.1"], "T1490": ["E3.1"]}
    assert assemble_reviewed_groups({"T1486": ["E2.1"]}, groups) == {
        "T1486": ["E1.1", "E2.1"],
    }
    invalid = {"T1486": ["E8.1"], "T1113": ["E2.1"]}
    assert assemble_reviewed_groups(invalid, groups) == invalid
    assert assemble_reviewed_groups({}, groups) == {}


def test_proof_assembly_still_requires_verified_evidence():
    runs = proof_experiment(read(LOCK)["proof_experiment"])
    for run in runs.values():
        assert run["before"]["review_items"] == []
        assert [item["technique"] for item in run["after"]["review_items"]] == run["expected_eligible"]
    assert runs["slate_missing_attribution"]["after"]["batch_state"] == "mixed"
    assert runs["windows_abstention"]["after"]["batch_state"] == "abstained"
