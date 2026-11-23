"""Replay stored diagnostic responses against frozen fictional cases and ATT&CK references."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from ai.config import load_config
from ai.mitre.stix import load_techniques
from eval.ai_mapping_ablation import ARMS, HISTORY, write_json
from eval.ai_retrieval_mapping import Prediction, fixture, gold_pairs, references, score, summary

# Analyst notes on what the supplied records actually establish or exclude.
# These never enter the model prompt, and are pending independent review.
EVIDENCE_NOTES = [
    ("confirmed", "E2", "An outsider completed a directory update under an existing domain account. E1 is unrelated."),
    ("prevented", "E2", "The controller rejected sign-on. The approved service account made the only completed update."),
    ("confirmed", "E1", "The cloud audit and owner establish an existing billing-account session and absent consent."),
    ("authorized", "E1", "Written delegation explains the completed cloud billing session."),
    ("confirmed", "E2", "A snapshot and change log confirm assignment of a cloud administrator role. The separate session-use alert was withdrawn."),
    ("prevented", "E2", "The request was rejected and the proposed role never took effect."),
    ("confirmed", "E1", "An intruder disabled existing accounts and their owners immediately lost access."),
    ("authorized", "E1", "Signed offboarding and verified departures explain the disabled accounts."),
    ("confirmed", "E2", "Screen images and matching telemetry establish collection of live desktop images. No remote session is established."),
    ("simulated", "E2", "The approved usability test generated mock images. No incident screen capture occurred."),
    ("confirmed", "E1", "The intruder collected files already stored on the local workstation."),
    ("unconfirmed", "E1", "A forwarded rumor alleges copying, with no trusted read or copy event."),
    ("confirmed", "E2", "Collection occurred directly on the remote mailbox service. The source explicitly excludes local mailbox files."),
    ("authorized", "E2", "The remote mailbox log reflects a sanctioned archive job. Intruder retrieval remains unverified."),
    ("confirmed", "E1", "Forensics attributes collection from an existing local mailbox archive. No corresponding remote access was found."),
    ("authorized", "E1", "The local mailbox archive was handled by the approved backup identity."),
    ("confirmed", "E2", "Lifecycle records corroborate power-down of the whole workstation. All services stopped as part of that shutdown."),
    ("authorized", "E2", "The shutdown is traced to scheduled, approved electrical maintenance."),
    ("confirmed", "E1", "Health logs and incident sign-off establish intentional termination of one service. The host continued running."),
    ("unconfirmed", "E1", "Service unhealthiness is recorded, but deliberate termination and its cause are uncorroborated."),
    ("confirmed", "E2", "Independent telemetry establishes that existing Windows events were emptied. Future logging is not the behavior described."),
    ("unconfirmed", "E2", "Only a forwarded summary alleges clearing. A collector gap cannot corroborate a clearing event."),
    ("confirmed", "E1", "Two sources corroborate stopping future logging. Older events remain, with no clearing observed."),
    ("simulated", "E1", "The corrected record shows normal collection and traces the alert to a tabletop exercise."),
    ("confirmed", "E2", "Telemetry and the final incident report corroborate listing running processes."),
    ("authorized", "E2", "The process list was produced by approved diagnostics."),
    ("confirmed", "E1", "The examiner confirms OS and architecture discovery. A process listing is not reported."),
    ("unconfirmed", "E1", "An untrusted ticket asks for inventory collection. There is no matching endpoint activity."),
    ("confirmed", "E2", "Recovered browser artifacts corroborate enumeration of bookmarks and history."),
    ("simulated", "E2", "The record requesting a technique label is from an unrelated exercise. No browser enumeration was observed."),
    ("confirmed", "E1", "The independent endpoint review establishes enumeration of security products, including endpoint protection."),
    ("authorized", "E1", "The signed record attributes endpoint security inventory to the approved compliance job."),
]


# Author-review anchors for the distinguishing action and its source.
ACTION_ANCHORS = {
    "fresh-01": ("completed staff-directory update", "existing Active Directory domain account"),
    "fresh-03": ("completed session", "already-issued cloud billing account"),
    "fresh-05": ("additional cloud administrator role was assigned", "existing account"),
    "fresh-07": ("disabled existing staff accounts",),
    "fresh-09": ("intruder acquiring those screen images",),
    "fresh-11": ("copied stored project reports", "local workstation"),
    "fresh-13": ("collected messages", "remote mailbox service"),
    "fresh-15": ("gathering stored messages", "local mailbox archive"),
    "fresh-17": ("powered down the whole workstation",),
    "fresh-19": ("terminated the payroll worker service",),
    "fresh-21": ("emptying the Windows event logs",),
    "fresh-23": ("disabled future Windows event logging",),
    "fresh-25": ("listed processes currently running",),
    "fresh-27": ("gathered the affected system's operating system version",),
    "fresh-29": ("enumerated the user's browser bookmarks and browsing history",),
    "fresh-31": ("enumerated the security products",),
}


def ranks_at(technique_id, ranks):
    return ranks.index(technique_id) + 1 if technique_id in ranks else None


def inspect_response(case, row, ranking, lookup, config, disposition, evidence_id):
    gold = gold_pairs(case)
    expected_ids = set(case["expected"])
    raw_pairs = {tuple(pair) for pair in row["score"]["raw_pairs"]}
    candidate_ids = row["context_ids"]
    missing = gold - raw_pairs
    extra = raw_pairs - gold
    issues = []
    if not row["score"]["contract"]:
        issues.append("invalid_response")
    if missing and any(tid not in candidate_ids for tid, _ in missing) and candidate_ids:
        issues.append("retrieval_miss")
    if missing and row["score"]["explicit_abstention"] and expected_ids.intersection(candidate_ids):
        issues.append("retrieved_but_abstained")
    if missing and any(tid not in expected_ids for tid, _ in extra) and expected_ids.intersection(candidate_ids):
        issues.append("retrieved_but_wrong_technique")
    if any(tid in expected_ids for tid, _ in extra) or row["score"]["blocked"]:
        issues.append("evidence_technique_mismatch")
    if extra:
        issues.append("unsupported_positive_against_author_labels")
    if missing and row["score"]["explicit_abstention"] and not candidate_ids:
        issues.append("abstention_without_references")
    verdicts = []
    if row["score"]["contract"]:
        for mapping in Prediction.model_validate_json(row["raw"]).mappings:
            tid, rid = mapping.technique_id, mapping.record_id
            evidence = case["records"].get(rid, "")
            pair = (tid, rid)
            binding = len(mapping.quote.strip()) >= 8 and mapping.quote.strip() in evidence
            if not binding:
                support = "quote_not_in_record"
            elif disposition != "confirmed":
                support = f"quoted_record_does_not_establish_adversary_action_{disposition}"
            elif rid != evidence_id:
                support = "cited_record_does_not_describe_the_confirmed_action"
            elif pair not in gold:
                support = "observed_behavior_does_not_establish_this_technique_under_author_rubric"
            elif all(anchor.casefold() in mapping.quote.casefold() for anchor in ACTION_ANCHORS[case["id"]]):
                support = "quote_contains_distinguishing_action_anchor_in_supportive_record"
            else:
                support = "record_supports_author_pair_but_quote_omits_part_of_action_anchor"
            technique = lookup.get(tid)
            parent = technique.parent_id if technique else None
            gold_parents = {lookup[expected].parent_id for expected in expected_ids}
            relation = "exact_id" if tid in expected_ids else "broader_parent" if tid in gold_parents else (
                "more_specific_child" if parent in expected_ids else
                "different_subtechnique" if parent and parent in gold_parents else "other_id")
            verdicts.append({**mapping.model_dump(), "source_record": evidence, "quote_verbatim": binding,
                             "matches_author_pair": pair in gold, "supplied_reference": tid in candidate_ids,
                             "reference_rank": ranks_at(tid, ranking), "scope_relation": relation,
                             "analyst_record_support": support})
    if extra and disposition != "confirmed" and "evidence_technique_mismatch" not in issues:
        issues.append("evidence_technique_mismatch")
    return {
        "arm": row["arm"], "exact": row["score"]["exact"], "contract": row["score"]["contract"],
        "abstained": row["score"]["explicit_abstention"], "expected_rank_and_context": {
            tid: {"retrieval_rank": ranks_at(tid, ranking), "supplied_to_model": tid in candidate_ids}
            for tid in sorted(expected_ids)},
        "supplied_references": [{**ref, "retrieval_rank": ranks_at(ref["technique_id"], ranking)}
                                for ref in references(candidate_ids, lookup, config)],
        "predictions": verdicts, "blocked": row["score"]["blocked"], "issues": issues,
        "first_actionable_failure": issues[0] if issues else None,
    }


def run(output):
    cases = fixture("evaluation")
    config = load_config(load_env=False).mitre
    lookup = {technique.technique_id: technique for technique in load_techniques(config)}
    new_ranks = json.loads((output / "retrieval.json").read_bytes())["ranked_ids"]
    old_ranks = json.loads((HISTORY / "retrieval.json").read_bytes())["ranked_ids"]["evaluation"]
    rows = defaultdict(list)
    recounted = defaultdict(list)
    for location in (HISTORY, output):
        for line in (location / "responses.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if location == HISTORY and row.get("split") != "evaluation":
                continue
            rows[row["id"]].append(row)
    traces = []
    for case, (disposition, evidence_id, note) in zip(cases, EVIDENCE_NOTES, strict=True):
        cid = case["id"]
        anchors = ACTION_ANCHORS.get(cid, ())
        if any(anchor.casefold() not in case["records"][evidence_id].casefold() for anchor in anchors):
            raise ValueError(f"Analyst anchor is absent from the source in {cid}")
        inspected = []
        for row in rows[cid]:
            recount = score(case, row["raw"], set(lookup))
            if json.dumps(recount, sort_keys=True) != json.dumps(row["score"], sort_keys=True):
                raise ValueError(f"Stored score mismatch in {cid}, {row['arm']}")
            arm = row["arm"]
            recounted[arm].append({"score": recount})
            if arm in ARMS:
                ranking = new_ranks[cid][ARMS[arm][0]]
            else:
                historical_method = {"no_rag": None, "tfidf": "tfidf"}.get(arm, "hybrid_e5")
                ranking = old_ranks[cid][historical_method] if historical_method else []
            inspected.append(inspect_response(case, row, ranking, lookup, config, disposition, evidence_id))
        expected_arms = set(ARMS) | {"tfidf", "challenger", "oracle", "evidence_first", "no_rag"}
        if {row["arm"] for row in inspected} != expected_arms or len(inspected) != len(expected_arms):
            raise ValueError(f"Incomplete arm coverage in {cid}")
        traces.append({"id": cid, "family": case["family"], "records": case["records"],
                       "author_expected_pairs": sorted(gold_pairs(case)), "analyst_disposition": disposition,
                       "decisive_record": evidence_id, "analyst_note": note, "analyst_action_anchors": anchors,
                       "independent_label_review": "pending",
                       "review_discriminator": {
                           "fresh-01": "Domain account action versus whether unauthorized existing-account use is established",
                           "fresh-03": "Existing cloud account session versus cloud role change",
                           "fresh-13": "Remote mailbox service versus local archive",
                           "fresh-15": "Local archive versus remote mailbox service",
                           "fresh-17": "Whole-host shutdown versus single-service termination",
                           "fresh-19": "Single-service termination versus whole-host shutdown",
                           "fresh-21": "Clearing existing events versus disabling future capture",
                           "fresh-23": "Disabling future capture versus clearing previous events",
                       }.get(cid), "arms": inspected})
    arm_metrics = json.loads((output / "mapping.json").read_bytes())["arms"]
    for arm, metrics in arm_metrics.items():
        if summary(recounted[arm]) != metrics:
            raise ValueError(f"Stored aggregate mismatch for {arm}")
    taxonomy = {arm: dict(Counter(issue for case in traces for row in case["arms"] if row["arm"] == arm
                                 for issue in row["issues"])) for arm in recounted}
    outside_context = {arm: [case["id"] for case in traces for row in case["arms"] if row["arm"] == arm
                             and any(p["matches_author_pair"] and not p["supplied_reference"]
                                     for p in row["predictions"])] for arm in recounted if arm != "no_rag"}
    write_json(output / "case-trace.json", {
        "label_provenance": "Frozen author rubric; analyst record review only, pending independent adjudication",
        "response_scores_independently_recounted": sum(map(len, recounted.values())),
        "taxonomy_case_counts": taxonomy, "correct_pairs_outside_context": outside_context, "cases": traces,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
