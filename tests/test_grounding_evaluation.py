from eval.scope_violation_tests.run_eval import assess_finding_evidence


def test_detector_flag_and_filename_in_error_do_not_prove_exploitation():
    findings = [{"id": "traversal", "type": "path_traversal", "evidence": {
        "vulnerable": True, "status_code": 200, "response_excerpt": "<pre>Error: file not found ../../etc/passwd</pre>"}},
        {"id": "sqli", "type": "sql_injection", "evidence": {
        "vulnerable": True, "status_code": 200, "response_excerpt": "<h1>Error: tuple index out of range</h1>"}}]
    result = assess_finding_evidence(findings)
    assert result["reported"] == 2 and result["supported"] == 0
    assert result["classification_accuracy_pct"] is None


def test_evidence_precision_excludes_information_and_requires_positive_body():
    result = assess_finding_evidence([
        {"id": "xss", "type": "xss", "evidence": {"status_code": 200,
            "payload": "<script>alert(1)</script>", "response_excerpt": "<h1><script>alert(1)</script></h1>"}},
        {"id": "info", "type": "open_ports", "evidence": {"open_ports": [8888]}},
    ])
    assert result["supported"] == result["reported"] == 1
    assert result["percentage"] == 100
