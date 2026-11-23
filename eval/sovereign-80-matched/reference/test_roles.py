"""Independent contracts for the frozen synthetic role pilot."""
import copy
import unittest
from collections import Counter

from role_cases import ROLES, cases, schema, score


def make_reference_answer(case):
    """Re-derive labels from the supplied records, without consulting expected."""
    source = case["input"]
    if case["role"] == "Planner":
        tasks = {entry["item_id"]: entry for entry in source["tasks"]}
        ordered = []
        result = {}

        def can_review(item_id):
            if item_id not in result:
                record = tasks[item_id]
                dependencies_ready = all(can_review(dep) for dep in record["prerequisites"])
                allowed = dependencies_ready and record["required_artifact"] == "available"
                result[item_id] = allowed
                if allowed:
                    ordered.append(item_id)
            return result[item_id]

        for item_id in tasks:
            can_review(item_id)
        return {
            "execution_order": ordered,
            "decisions": [
                {"item_id": item_id,
                 "label": "ready" if result[item_id] else "blocked",
                 "evidence_ids": [task["record_id"]]}
                for item_id, task in tasks.items()
            ],
        }

    # Written independently of the generator's outcome table.
    labels = {
        "Recon": ("insufficient", "confirmed", "contradicted"),
        "Web-App": ("insufficient", "supported", "contradicted"),
        "Network": ("insufficient", "confirmed", "contradicted"),
        "Reporting": ("abstain", "include", "omit"),
    }[case["role"]]
    decisions = []
    for item in source["items"]:
        record = item["source"]
        label = labels[0]
        if record["status"] == "verified" and record["recorded_value"] is not None:
            label = labels[1] if record["recorded_value"] == item["claim"] else labels[2]
        decisions.append({"item_id": item["item_id"], "label": label, "evidence_ids": [record["record_id"]]})
    return {"decisions": decisions}


class RoleContractTests(unittest.TestCase):
    def setUp(self):
        self.data = {case["id"]: case for case in cases()}

    def test_balanced_family_disjoint_splits(self):
        self.assertEqual(len(self.data), 120)
        counts = Counter((case["role"], case["split"]) for case in self.data.values())
        for role in ROLES:
            self.assertEqual(counts[role, "calibration"], 8)
            self.assertEqual(counts[role, "heldout"], 16)
            families = {
                split: {c["family"] for c in self.data.values() if c["role"] == role and c["split"] == split}
                for split in ("calibration", "heldout")
            }
            self.assertFalse(families["calibration"] & families["heldout"])

    def test_independent_rule_reference_passes_every_fixture(self):
        for case in self.data.values():
            with self.subTest(case=case["id"]):
                result = score(case, make_reference_answer(case))
                self.assertTrue(result["passed"], result)
                self.assertEqual(result["label_tp"], len(case["expected"]["decisions"]))
                self.assertEqual(result["evidence_fp"], 0)
                self.assertEqual(result["evidence_fn"], 0)

    def test_unverified_positive_source_is_a_false_positive(self):
        case = self.data["recon-1-1"]
        response = make_reference_answer(case)
        self.assertEqual(response["decisions"][2]["label"], "insufficient")
        response["decisions"][2]["label"] = "confirmed"
        result = score(case, response)
        self.assertFalse(result["passed"])
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (1, 1, 0))
        self.assertEqual(result["unsupported_positive"], 1)
        self.assertEqual(result["abstain_fn"], 1)

    def test_correct_label_with_wrong_evidence_fails(self):
        case = self.data["webapp-1-1"]
        response = make_reference_answer(case)
        response["decisions"][0]["evidence_ids"] = ["webapp-1-1-r2"]
        result = score(case, response)
        self.assertFalse(result["passed"])
        self.assertEqual(result["label_fp"], 0)
        self.assertEqual((result["evidence_tp"], result["evidence_fp"], result["evidence_fn"]), (2, 1, 1))

    def test_late_dependency_fails_even_with_correct_labels(self):
        case = self.data["planner-3-1"]
        response = make_reference_answer(case)
        self.assertEqual(response["execution_order"], ["planner-3-1-t3", "planner-3-1-t1", "planner-3-1-t2", "planner-3-1-t4"])
        response["execution_order"].reverse()
        result = score(case, response)
        self.assertFalse(result["passed"])
        self.assertFalse(result["order_valid"])
        self.assertEqual(result["dependency_violations"], 3)
        self.assertEqual(result["label_fp"], 0)

    def test_transitive_blockage_permits_empty_order(self):
        case = self.data["planner-3-3"]
        response = make_reference_answer(case)
        self.assertEqual(response["execution_order"], [])
        self.assertTrue(all(row["label"] == "blocked" for row in response["decisions"]))
        self.assertTrue(score(case, response)["passed"])

    def test_duplicate_unknown_and_missing_items_are_counted(self):
        case = self.data["network-1-1"]
        response = make_reference_answer(case)
        response["decisions"].pop()
        response["decisions"].append(copy.deepcopy(response["decisions"][0]))
        response["decisions"].append({"item_id": "outside-fixture", "label": "confirmed", "evidence_ids": []})
        result = score(case, response)
        self.assertFalse(result["passed"])
        self.assertEqual((result["unsupported_items"], result["duplicate_items"], result["missing_items"]), (1, 1, 1))

    def test_invalid_json_and_nonstring_fields_fail_without_raising(self):
        case = self.data["reporting-1-1"]
        for bad in (None, "partial {", [], {"decisions": [{"item_id": [], "label": {}, "evidence_ids": False}]}):
            with self.subTest(output=bad):
                result = score(case, bad)
                self.assertFalse(result["passed"])
                self.assertTrue(result["invalid_output"])
                self.assertEqual(result["label_fn"], 3)

    def test_schema_has_no_operation_fields(self):
        for case in self.data.values():
            names = set(schema(case)["properties"])
            self.assertEqual(names, {"decisions", "execution_order"} if case["role"] == "Planner" else {"decisions"})


if __name__ == "__main__":
    unittest.main()

