"""Generate a mock response fixture for offline pipeline validation ONLY.

The generated responses are deliberately derived from the frozen expected answers;
a run using them is a wiring test and must never be reported as model accuracy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import frozen_protocol as fp


def topo(deps: dict[str, list[str]]) -> list[str]:
    done: list[str] = []
    while len(done) < len(deps):
        for key, parents in deps.items():
            if key not in done and all(p in done for p in parents):
                done.append(key)
                break
        else:
            raise ValueError("cycle in mock dependency graph")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = fp.load_manifest()
    responses = {}
    for i, entry in enumerate(fp.heldout_entries(manifest)):
        case = entry["case"]
        payload = {"decisions": [
            {"item_id": row["item_id"], "label": row["label"],
             "evidence_ids": list(row["evidence_ids"])}
            for row in case["expected"]["decisions"]
        ]}
        if case["role"] == "Planner":
            payload["execution_order"] = topo(case["expected"]["dependencies"])
        content = json.dumps(payload, ensure_ascii=False)
        cell = {"status": 200, "model": fp.MODEL, "content": content,
                "finish_reason": "stop", "reasoning_tokens": 0,
                "usage": {"prompt_tokens": 445, "completion_tokens": 140}}
        cells = [cell]
        if i % 7 == 0:
            cells.insert(0, {**cell, "content": "not json", "usage": {
                "prompt_tokens": 445, "completion_tokens": 384}})
        if i % 5 == 0:
            broken = json.loads(content)
            broken["decisions"][0]["evidence_ids"] = []
            cells[-1] = {**cell, "content": json.dumps(broken, ensure_ascii=False)}
        responses[case["id"]] = cells[0] if len(cells) == 1 else {"sequence": cells}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"responses": responses}, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"wrote {len(responses)} mock cases to {args.output}")


if __name__ == "__main__":
    main()
