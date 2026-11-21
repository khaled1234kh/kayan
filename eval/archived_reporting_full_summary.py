"""Compare a bounded swap policy with append-only archived summaries offline."""

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from eval.archived_reporting_local_ranking import canonical, prepare_case
from eval.archived_reporting_selection import selection_metrics
from pentagi.agents.archived_reporting import MAX_HIGHLIGHTS, _selection_options, compose


FIXTURE = Path(__file__).with_name("fixtures") / "ai" / "archived_reporting_full_summary_v1.json"
FOCUS_ROLES = frozenset({"actor", "authorization"})
TECHNIQUE = "T1486"


def rebalance_selection(report, selection, *, max_replacements):
    original = compose(report, json.dumps(selection), supplement_actions=True)
    ids = selection["highlights"]
    if len(ids) != MAX_HIGHLIGHTS:
        return original, []

    excerpts, _ = _selection_options(report, True)
    # This frozen comparison contains repeated techniques, using occurrence aliases.
    if not set(ids) <= excerpts.keys():
        raise ValueError("Expected occurrence-aware selection references")
    events = {key: (finding["technique"], finding["occurrence"])
              for key, (finding, _) in excerpts.items()}
    roles = {key: frozenset(source["roles"]) for key, (_, source) in excerpts.items()}
    action_events = {events[key] for key in ids if "mechanic" in roles[key]}
    shown = Counter(events[key] for key in ids)
    missing = {}
    for key, event in events.items():
        if "mechanic" in roles[key] and event not in action_events:
            missing.setdefault(event, key)
    # Prefer rescuing otherwise unseen occurrences, then improve represented ones.
    ordered_actions = sorted(missing.items(), key=lambda pair: pair[0] in shown)
    next_ids = list(ids)
    changes = []
    for event, action in ordered_actions:
        if len(changes) >= max_replacements:
            break
        # Reverse order preserves higher-ranked context when there is a choice.
        for index in range(len(next_ids) - 1, -1, -1):
            key = next_ids[index]
            old_event = events[key]
            if roles[key] and roles[key] <= FOCUS_ROLES and (old_event == event or shown[old_event] > 1):
                next_ids[index] = action
                shown[old_event] -= 1
                shown[event] += 1
                changes.append({"index": index, "removed": key, "added": action})
                break
    return compose(report, json.dumps({**selection, "highlights": next_ids})), changes


def case_input(case):
    authorized = set(case.get("authorized", []))
    events = [
        {"technique": TECHNIQUE, "authorized": number in authorized,
         "action": f"The fictional {asset} ledger recorded encryption of its working archive.",
         "outcome": f"The fictional {asset} review confirmed whether its working copies remained available."}
        for number, asset in enumerate(case["assets"], 1)
    ]
    report, _ = prepare_case({"id": case["id"], "events": events}, {
        "model": "no-model-offline-replay", "keep_alive": "0", "options": {},
    })
    dispositions = {"admitted": len(report["findings"]), "withheld": len(report["withheld"])}
    if dispositions != case["expected"]:
        raise ValueError(f"Unexpected admission counts for {case['id']}")
    selection = {"highlights": [f"F{event}/S{source}" for event, source in case["selection"]],
                 "recommendations": ["T1486-1", "T1486-2"], "emphasis": "observed_impact"}
    oracle = {"highlights": [[TECHNIQUE, f"event-{event}", f"E{event}.{source}"]
                             for event, source in case["preferred"]],
              "recommendations": selection["recommendations"]}
    return report, selection, oracle


def score_case(case, max_replacements):
    report, selection, oracle = case_input(case)
    original = compose(report, json.dumps(selection), supplement_actions=True)
    updated, changes = rebalance_selection(report, selection, max_replacements=max_replacements)
    before, after = (selection_metrics(result, oracle) for result in (original, updated))
    before_h, after_h = before["highlights"], after["highlights"]
    removed = {entry["removed"] for entry in changes}
    retained = [ref for key, ref in zip(selection["highlights"], before_h["references"], strict=True)
                if key not in removed]
    after_retained = [ref for ref in after_h["references"] if ref in retained]
    before_occurrences = {(ref[0], ref[1]) for ref in before_h["references"]}
    after_occurrences = {(ref[0], ref[1]) for ref in after_h["references"]}
    return {
        "id": case["id"], "group": case["group"], "archive_sha256": report["source_sha256"],
        "selection_sha256": sha256(canonical(selection)).hexdigest(),
        "baseline": before, "candidate": after, "changes": changes,
        "retained_refs": len(retained), "retained_order": retained == after_retained,
        "original_occurrences_retained": before_occurrences <= after_occurrences,
        "verified_decisions_and_controls_unchanged": all(
            original[key] == updated[key] for key in ("findings", "withheld", "recommendations", "emphasis")
        ),
        "action_gain": after["published_coverage"]["action_covered_occurrences"]
                       - before["published_coverage"]["action_covered_occurrences"],
        "preference_loss": before_h["matching"] - after_h["matching"],
    }


def evaluate():
    raw = FIXTURE.read_bytes()
    spec = json.loads(raw)
    criteria = spec["criteria"]
    rows = [score_case(case, spec["max_replacements"]) for case in spec["cases"]]
    checks = {
        "decision_and_control_integrity": all(row["verified_decisions_and_controls_unchanged"] for row in rows),
        "capacity": all(row["candidate"]["highlights"]["returned"] == MAX_HIGHLIGHTS for row in rows),
        "original_reference_order_and_occurrences_retained": all(
            row["retained_order"] and row["original_occurrences_retained"] and
            row["retained_refs"] >= criteria["minimum_original_refs_retained"] for row in rows
        ),
        "unchanged_controls": all(not row["changes"] for row in rows if row["group"] == "retain"),
        "action_coverage_improves": sum(row["action_gain"] for row in rows) >= criteria["minimum_total_gain"],
        "no_case_exceeds_preference_loss_budget": all(
            row["preference_loss"] <= criteria["maximum_preference_loss_per_case"] for row in rows
        ),
    }
    return {"protocol": spec["protocol"], "fixture_sha256": sha256(raw).hexdigest(),
            "decision": checks, "candidate_qualifies": all(checks.values()), "cases": rows}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, ensure_ascii=True))
