"""Prepare blinded forms and compare two completed human ATT&CK reviews."""

import argparse
import json
from collections import Counter
from pathlib import Path

from ai.config import load_config
from ai.mitre.stix import load_techniques
from eval.ai_retrieval_mapping import digest

DISPOSITIONS = (
    "confirmed_adversary", "authorized", "prevented", "unconfirmed",
    "insufficient", "contradictory", "simulated",
)
FIELDS = ("observed_action", "evidence_reliability", "contradictions", "rationale")
INSTRUCTIONS = [
    "Review independently using Enterprise ATT&CK 20.1. Do not use benchmark scores, model outputs or another reviewer.",
    "Describe the observed action, select its evidence disposition and mark whether the mapping is genuinely ambiguous.",
    "Use the most specific defensible active technique and its supporting record IDs. An empty mappings object means no mapping.",
    "A confirmed action can remain unmapped if the evidence does not distinguish a technique. Record that uncertainty.",
    "Document source reliability, contradictions and their disposition. Cite facts rather than matching a keyword or product name.",
    "Complete every row. Use None observed as text when appropriate. Return the file privately to the study coordinator.",
]


def prepare(packet, review_id):
    raw = packet.read_bytes()
    cases = json.loads(raw)["cases"]
    if not cases or len(cases) != len({case["id"] for case in cases}):
        raise ValueError("The blinded packet must have nonempty, unique cases")
    return {
        "version": 1, "packet_sha256": digest(raw), "reviewer_id": review_id,
        "dispositions": DISPOSITIONS, "instructions": INSTRUCTIONS,
        "cases": [{"id": case["id"], "records": case["records"], "disposition": None, "ambiguous": None,
                   "mappings": None, **dict.fromkeys(FIELDS)}
                  for case in sorted(cases, key=lambda row: digest(row["id"].encode()))],
    }


def validate(sheet, packet, active_ids):
    if sheet["packet_sha256"] != packet["packet_sha256"] or not sheet["reviewer_id"].strip():
        raise ValueError("The completed form does not identify its frozen packet or reviewer")
    expected = {row["id"]: row["records"] for row in packet["cases"]}
    rows = {row["id"]: row for row in sheet["cases"]}
    if len(rows) != len(sheet["cases"]) or rows.keys() != expected.keys():
        raise ValueError("Missing, duplicate or unexpected case IDs")
    for cid, row in rows.items():
        if (row["records"] != expected[cid] or row["disposition"] not in DISPOSITIONS
                or not isinstance(row["ambiguous"], bool) or not isinstance(row["mappings"], dict)
                or any(not isinstance(row[key], str) or not row[key].strip() for key in FIELDS)):
            raise ValueError(f"Incomplete or altered review row {cid}")
        mappings = row["mappings"]
        if mappings and row["disposition"] != "confirmed_adversary":
            raise ValueError(f"Positive mapping for a non-confirmed disposition in {cid}")
        for tid, evidence in mappings.items():
            if (tid not in active_ids or not isinstance(evidence, list) or not evidence
                    or any(not isinstance(rid, str) or rid not in expected[cid] for rid in evidence)
                    or len(evidence) != len(set(evidence))):
                raise ValueError(f"Invalid technique or evidence record in {cid}")
    return rows


def agreement(first, second, packet, active_ids):
    if first["reviewer_id"].strip().casefold() == second["reviewer_id"].strip().casefold():
        raise ValueError("Two different reviewers are required")
    reviewers = [validate(sheet, packet, active_ids) for sheet in (first, second)]
    pairs = [(reviewers[0][cid], reviewers[1][cid]) for cid in sorted(reviewers[0])]
    total = len(pairs)
    metrics = {}
    for label, value in (
        ("disposition", lambda row: row["disposition"]),
        ("any_mapping", lambda row: bool(row["mappings"])),
        ("exact_technique_set", lambda row: frozenset(row["mappings"])),
        ("exact_technique_record_pairs", lambda row: frozenset(
            (tid, rid) for tid, ids in row["mappings"].items() for rid in ids)),
    ):
        decisions = [(value(a), value(b)) for a, b in pairs]
        matches = sum(a == b for a, b in decisions)
        left, right = (Counter(items) for items in zip(*decisions, strict=True))
        expected = sum(count * right[key] for key, count in left.items()) / (total * total)
        metrics[label] = {"matches": matches, "total": total, "agreement": matches / total,
                          "cohens_kappa": (matches / total - expected) / (1 - expected) if expected < 1 else None}
    disagreements = [{"id": a["id"], "reviewer_a": a, "reviewer_b": b} for a, b in pairs
                     if a["disposition"] != b["disposition"] or a["ambiguous"] or b["ambiguous"]
                     or {tid: set(ids) for tid, ids in a["mappings"].items()}
                     != {tid: set(ids) for tid, ids in b["mappings"].items()}]
    return {"packet_sha256": packet["packet_sha256"], "metrics": metrics, "requires_adjudication": disagreements}


def save(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "compare"):
        sub = commands.add_parser(command)
        sub.add_argument("packet", type=Path)
        sub.add_argument("output", type=Path)
        if command == "prepare":
            sub.add_argument("reviewer_id")
        else:
            sub.add_argument("first", type=Path)
            sub.add_argument("second", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        save(args.output, prepare(args.packet, args.reviewer_id))
    else:
        catalogue = {t.technique_id for t in load_techniques(load_config(load_env=False).mitre)}
        save(args.output, agreement(json.loads(args.first.read_bytes()), json.loads(args.second.read_bytes()),
                                   prepare(args.packet, ""), catalogue))
