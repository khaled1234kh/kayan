from copy import deepcopy

import pytest

from eval.attack_experiment_v2 import ROOT, read
from eval.cloud_frozen_diagnostic import MODEL, outgoing
from eval.cloud_reasoning_budget_v2 import check_probe, prepare
from eval.attack_evidence_v2 import compact


def test_only_generation_parameters_change_in_the_twelve_diagnostics():
    from tests.private_artifacts import require_private
    require_private('.build/cloud-real-comparison-v1-prepared.json')
    original = read(ROOT / ".build/cloud-real-comparison-v1-prepared.json")
    frozen = prepare(original)
    assert len(frozen["stage_b"]) == 12
    for cell in frozen["stage_b"]:
        parent = outgoing(original["cases"][cell["case"]]["cloud_drafts"][cell["arm"]], cell["arm"])
        assert cell["request"] == {**parent, "reasoning_effort": "none", "max_tokens": 1024}
    assert frozen["stage_a"]["request"]["response_format"] == frozen["stage_b"][2]["request"]["response_format"]


def test_probe_requires_nonempty_exact_answer_zero_reasoning_and_no_clamp():
    expected = {"facts": [{"technique": "T1685.005", "anchor": "E1.1", "cite": "E1.1",
                           "role": "mechanic", "value": "observed"}]}
    wire = {"model": MODEL, "choices": [{"finish_reason": "stop", "message": {"content": compact(expected)}}],
            "usage": {"completion_tokens_details": {"reasoning_tokens": 0}}}
    check_probe(200, {}, wire, expected)
    for headers in ({"X-Plan-Output-Cap": "512"}, {"X-Mapped-Params": "reasoning_effort=low"}):
        with pytest.raises(ValueError):
            check_probe(200, headers, wire, expected)
    for content in ('{"facts":[]}', ''):
        altered = deepcopy(wire)
        altered["choices"][0]["message"]["content"] = content
        with pytest.raises(ValueError):
            check_probe(200, {}, altered, expected)
    altered = deepcopy(wire)
    del altered["usage"]["completion_tokens_details"]
    with pytest.raises(ValueError):
        check_probe(200, {}, altered, expected)
