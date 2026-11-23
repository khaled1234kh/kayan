"""Scoring and capacity proof for the v2 retrospective synthetic study."""
from collections import Counter
import json
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

VERSION = "attack-mapping-exploratory-v2"
MAX_ITEMS = 8
OUTPUT_TOKENS = 370
CONTEXT_TOKENS = 4096
# Qwen2 byte-level BPE: at most one token per input byte, plus boundary tokens.
BOUNDARY_RESERVE = 4
ROLES = {"action", "asset", "outcome", "actor", "authorization", "link"}
REQUIRED = ROLES - {"link"}
STATUSES = {"topic_only", "contradicts", "superseded", "action_only", "unresolved",
            "authorized", "unlinked", "corroborating"}
DISPOSITIONS = {"confirmed", "benign", "failed", "inconclusive"}


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    technique: str = Field(pattern=r"^T[0-9]{4}(\.[0-9]{3})?$")
    cite: str = Field(pattern=r"^E[1-9][0-9]*\.[1-9][0-9]*$")


class Response(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mappings: Annotated[list[Citation], Field(max_length=MAX_ITEMS)]


def compact(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def unique_keys(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"Duplicate JSON key {key}")
        result[key] = value
    return result


def parse(text):
    return json.loads(text, object_pairs_hook=unique_keys)


def spans(records):
    return {f"{rid}.{i}": line for rid, lines in records.items() for i, line in enumerate(lines, 1)}


def entry(tid, ref):
    return {"technique": tid, "cite": ref}


def witness(records, label, active, *, budget=OUTPUT_TOKENS):
    """Exhibit one scorable answer; discard cases without a certified witness."""
    if set(label) != {"disposition", "targets", "exceptions", "rationale"} or not label["rationale"].strip():
        raise ValueError("Incomplete scoring key")
    if set(records) != {f"E{i}" for i in range(1, len(records) + 1)} or not records:
        raise ValueError("Record IDs must be contiguous")
    if any(not isinstance(lines, list) or not lines or
           any(not isinstance(line, str) or not line.strip() for line in lines) for lines in records.values()):
        raise ValueError("Missing source statements")
    refs = spans(records)
    targets = label["targets"]
    if label["disposition"] not in DISPOSITIONS or bool(targets) != (label["disposition"] == "confirmed"):
        raise ValueError("Targets and disposition disagree")
    for tid, flagged in label["exceptions"].items():
        if (tid not in active or not flagged or not set(flagged) <= refs.keys()
                or not set(flagged.values()) <= STATUSES
                or ("corroborating" in flagged.values() and tid not in targets)):
            raise ValueError("Invalid exception annotation")
    # At most eight (count, byte cost) states per technique. A longer group can use
    # fewer bytes if it uses shorter addresses. Keep the cheapest witness per count.
    states = {0: (0, [])}
    for tid, spec in sorted(targets.items()):
        if tid not in active or set(spec) != {"atoms", "groups"} or not spec["groups"]:
            raise ValueError("Invalid target or absent evidence groups")
        groups = [frozenset(group) for group in spec["groups"]]
        atoms = spec["atoms"]
        if (len(set(groups)) != len(groups) or set.union(set(), *groups) != set(atoms)
                or not set(atoms) <= refs.keys() or set(atoms) & set(label["exceptions"].get(tid, {}))
                or any(not roles or len(set(roles)) != len(roles) or not set(roles) <= ROLES for roles in atoms.values())):
            raise ValueError("Inconsistent support atoms")
        choices = []
        for raw, group in zip(spec["groups"], groups, strict=True):
            if (not group or len(raw) != len(group) or any(other < group for other in groups)
                    or not REQUIRED <= set().union(*(atoms[ref] for ref in group))):
                raise ValueError("Evidence group is incomplete, duplicated or non-minimal")
            choices.append([entry(tid, ref) for ref in sorted(group)])
        following = {}
        for count, (cost, prefix) in states.items():
            for choice in choices:
                size = count + len(choice)
                length = cost + sum(len(compact(item)) + 1 for item in choice)
                if size <= MAX_ITEMS and (size not in following or length < following[size][0]):
                    following[size] = (length, prefix + choice)
        states = following
    if not states:
        raise ValueError("No complete answer fits the eight-citation schema")
    raw = min((compact({"mappings": parts}) for _, parts in states.values()), key=lambda s: (len(s), s))
    bound = len(raw.encode("utf-8")) + BOUNDARY_RESERVE
    if bound > budget:
        raise ValueError(f"No certified compact witness within {budget} output tokens (byte bound {bound})")
    if not score(records, label, raw, active)["exact"]:
        raise ValueError("Witness fails the actual scoring contract")
    return {"witness_entries": len(parse(raw)["mappings"]), "witness_output_token_upper_bound": bound,
            "witness": parse(raw)}


def score(records, label, raw, active, *, execution_error=None):
    refs = spans(records)
    citations = []
    error = execution_error
    if error is None:
        try:
            prediction = Response.model_validate(parse(raw))
            citations = [(row.technique, row.cite) for row in prediction.mappings]
            if len(set(citations)) != len(citations):
                raise ValueError("Duplicate citation")
        except (ValidationError, ValueError, TypeError) as exc:
            error = str(exc)
            citations = []
    expected = set(label["targets"])
    selected = {tid for tid, _ in citations}
    evidence, traced = {}, []
    bad_refs = 0
    for tid, ref in citations:
        spec = label["targets"].get(tid, {})
        if tid not in active:
            status = "unknown_technique"
        elif ref not in refs:
            status = "unknown_address"
        elif ref in spec.get("atoms", {}):
            status = "keyed_support"
        else:
            status = label["exceptions"].get(tid, {}).get(ref, "unkeyed")
        if status == "keyed_support":
            evidence.setdefault(tid, set()).add(ref)
        elif status != "corroborating":
            bad_refs += 1
        traced.append({"technique": tid, "cite": ref, "text": refs.get(ref), "status": status,
                       "roles": spec.get("atoms", {}).get(ref, [])})
    completed = set()
    pair_tp, pair_fn = set(), set()
    for tid, spec in label["targets"].items():
        eligible = evidence.get(tid, set())
        groups = [set(group) for group in spec["groups"]]
        full = [group for group in groups if group <= eligible]
        if full:
            completed.add(tid)
        # Score one reference group. Extra valid alternatives are neutral at the pair level.
        group = min(full or groups, key=lambda g: (len(g - eligible), -len(g & eligible), len(g), sorted(g)))
        gold = {(tid, ref.split(".")[0]) for ref in group}
        hits = {(tid, ref.split(".")[0]) for ref in eligible & group}
        pair_tp.update(hits)
        pair_fn.update(gold - hits)
    # Addresses can be wrong inside the right record. The trace exposes this
    # separately; the pair metric counts each distinct record at most once per sign.
    invalid_pairs = {(r["technique"], r["cite"].split(".")[0]) for r in traced
                     if r["status"] not in {"keyed_support", "corroborating"}}
    valid_pairs = {(r["technique"], r["cite"].split(".")[0]) for r in traced
                   if r["status"] in {"keyed_support", "corroborating"}}
    unsupported = selected - completed
    missed = expected - completed
    abstain = error is None and not selected
    return {"disposition": label["disposition"], "contract": error is None, "error": error,
            "abstain": abstain, "exact": error is None and not unsupported and not missed and not bad_refs,
            "tech_tp": len(selected & expected), "tech_fp": len(selected - expected), "tech_fn": len(expected - selected),
            "groups_complete": len(completed), "targets": len(expected), "unsupported": len(unsupported),
            "missed": len(missed), "citations": len(traced), "keyed": sum(len(v) for v in evidence.values()),
            "corroborating": sum(r["status"] == "corroborating" for r in traced), "bad_cites": bad_refs,
            "pair_tp": len(pair_tp), "pair_fp": len(invalid_pairs - valid_pairs), "pair_fn": len(pair_fn),
            "trace": traced, "completed": sorted(completed), "selected": sorted(selected),
            "cost": 2 * len(unsupported) + len(missed) + bad_refs + 3 * int(error is not None)}


def summarise(rows):
    def rate(n, d):
        return n / d if d else None

    def f1(t, f, m):
        return rate(2 * t, 2 * t + f + m)

    counts = Counter()
    for row in rows:
        counts.update({k: int(v) for k, v in row.items() if isinstance(v, (int, bool))})
    known_neg = [r for r in rows if r["disposition"] in {"benign", "failed"}]
    uncertain = [r for r in rows if r["disposition"] == "inconclusive"]
    classes = Counter(r["status"] for row in rows for r in row["trace"])
    return {"cases": len(rows), "counts": dict(counts), "citation_classes": dict(classes),
            "technique_f1": f1(counts["tech_tp"], counts["tech_fp"], counts["tech_fn"]),
            "record_pair_f1": f1(counts["pair_tp"], counts["pair_fp"], counts["pair_fn"]),
            "complete_group_recall": rate(counts["groups_complete"], counts["targets"]),
            "citation_relevance": rate(counts["keyed"] + counts["corroborating"], counts["citations"]),
            "known_negative_specificity": rate(sum(r["abstain"] for r in known_neg), len(known_neg)),
            "inconclusive_abstention": rate(sum(r["abstain"] for r in uncertain), len(uncertain)),
            "abstention_rate": rate(counts["abstain"], len(rows)), "mean_cost": rate(counts["cost"], len(rows))}

