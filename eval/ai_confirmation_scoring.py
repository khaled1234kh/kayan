"""Score a frozen, adjudicated defensive ATT&CK confirmation comparison."""

from collections import defaultdict
from random import Random

from pydantic import ValidationError

from eval.ai_retrieval_mapping import Prediction


def score_case(label, records, raw, active_ids, error=None, *, transport_error=False):
    released, attempted, blocked = set(), set(), []
    try:
        prediction = None if error else Prediction.model_validate_json(raw)
    except ValidationError:
        prediction = None
    if prediction is not None:
        for item in prediction.mappings:
            pair = (item.technique_id, item.record_id)
            attempted.add(pair)
            quote = item.quote.strip()
            if item.technique_id not in active_ids:
                blocked.append((*pair, "inactive_or_unknown_id"))
            elif len(quote) < 8 or quote not in records.get(item.record_id, ""):
                blocked.append((*pair, "quote_mismatch"))
            elif len(item.justification.strip()) < 8:
                blocked.append((*pair, "missing_justification"))
            else:
                released.add(pair)
    tp, fn, compatible, satisfied, chosen = set(), set(), set(), [], {}
    for tid, groups in sorted(label.evidence_sets.items()):
        gold = [{(tid, rid) for rid in group} for group in groups]
        complete = [group for group in gold if group <= released]
        if complete:
            reference = min(complete, key=lambda group: (-len(group), sorted(group)))
            tp.update(reference)
            compatible.update(set.union(*complete))
            satisfied.append(tid)
        else:
            reference = min(gold, key=lambda group: (-len(released & group), len(group), sorted(group)))
            fn.update(reference)
        chosen[tid] = sorted(rid for _, rid in reference)
    fp = attempted - compatible
    scored = label.resolution == "score"
    abstained = prediction is not None and not attempted
    return {
        "scored": scored, "positive": bool(label.evidence_sets), "contract": prediction is not None,
        "abstained": abstained, "execution_failed": error is not None, "transport_error": transport_error,
        "exact": scored and prediction is not None and not fp and not fn and not blocked,
        "satisfied_techniques": satisfied, "expected_techniques": len(chosen), "chosen_evidence_sets": chosen,
        "tp": sorted(tp), "fp": sorted(fp), "fn": sorted(fn), "binding_blocks": blocked,
        "attempted_pairs": sorted(attempted), "mechanically_eligible_pairs": sorted(released),
    }


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def aggregate(rows, approval):
    scored = [row for row in rows if row["scored"]]
    positive = [row for row in scored if row["positive"]]
    negative = [row for row in scored if not row["positive"]]
    tp, fp, fn = (sum(len(row[key]) for row in scored) for key in ("tp", "fp", "fn"))
    weighted = approval.unsupported_pair_weight * fp + approval.missed_pair_weight * fn
    return {
        "attempted_cases": len(rows), "scored_cases": len(scored), "excluded_ambiguous": len(rows) - len(scored),
        "positive_cases": len(positive), "negative_cases": len(negative),
        "exact": sum(row["exact"] for row in scored), "exact_rate": ratio(sum(row["exact"] for row in scored), len(scored)),
        "positive_exact": sum(row["exact"] for row in positive), "negative_exact": sum(row["exact"] for row in negative),
        "positive_exact_rate": ratio(sum(row["exact"] for row in positive), len(positive)),
        "negative_exact_rate": ratio(sum(row["exact"] for row in negative), len(negative)),
        "positive_case_recall": ratio(sum(bool(row["satisfied_techniques"]) for row in positive), len(positive)),
        "negative_specificity": ratio(sum(row["abstained"] for row in negative), len(negative)),
        "tp": tp, "fp": fp, "fn": fn, "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "abstentions": sum(row["abstained"] for row in rows),
        "abstention_rate": ratio(sum(row["abstained"] for row in rows), len(rows)),
        "contract_successes": sum(row["contract"] for row in rows),
        "transport_errors": sum(row["transport_error"] for row in rows),
        "execution_errors": sum(row["execution_failed"] for row in rows),
        "error_rate": ratio(sum(not row["contract"] for row in rows), len(rows)),
        "citation_blocked_cases": sum(bool(row["binding_blocks"]) for row in rows),
        "citation_blocked_predictions": sum(len(row["binding_blocks"]) for row in rows),
        "weighted_error_per_case": ratio(weighted, len(scored)),
    }


def compare(baseline, challenger, approval, *, draws=10_000):
    groups = defaultdict(list)
    for a, b in zip(baseline, challenger, strict=True):
        if (a["id"], a["family"], a["scored"]) != (b["id"], b["family"], b["scored"]):
            raise ValueError("Unmatched or partially scored comparison")
        groups[a["family"]].append((a, b))
    left, right = (aggregate(rows, approval) for rows in (baseline, challenger))
    families = []
    for name, members in sorted(groups.items()):
        a_rows, b_rows = zip(*members, strict=True)
        a, b = aggregate(a_rows, approval), aggregate(b_rows, approval)
        count = a["scored_cases"]
        families.append({"family": name, "cases": [row["id"] for row in a_rows], "scored_cases": count,
                         "exact_challenger_minus_baseline": b["exact"] - a["exact"],
                         "weighted_baseline_minus_challenger": count * (
                             (a["weighted_error_per_case"] or 0) - (b["weighted_error_per_case"] or 0))})
    rng = Random(391)
    samples = []
    for _ in range(draws):
        resampled = rng.choices(families, k=len(families))
        count = sum(row["scored_cases"] for row in resampled)
        if count:
            samples.append(tuple(sum(row[key] for row in resampled) / count for key in (
                "exact_challenger_minus_baseline", "weighted_baseline_minus_challenger")))

    def interval(values):
        values = sorted(values)
        return [values[int(q * (len(values) - 1))] for q in (.025, .975)]

    exact, weighted = (interval(col) for col in zip(*samples, strict=True))
    gain = left["weighted_error_per_case"] - right["weighted_error_per_case"]
    specificity_loss = left["negative_specificity"] - right["negative_specificity"]
    quality_ok = all(arm["contract_successes"] == arm["attempted_cases"] for arm in (left, right))
    promote = (quality_ok and gain >= approval.min_weighted_improvement_per_case
               and specificity_loss <= approval.max_negative_specificity_loss and weighted[0] > 0
               and (approval.interval_requirement == "above_zero"
                    or weighted[0] >= approval.min_weighted_improvement_per_case))
    return {"baseline": left, "challenger": right, "per_family": families,
            "bootstrap": {"draws": draws, "usable_draws": len(samples), "seed": 391,
                          "exact_difference_95": exact, "weighted_improvement_95": weighted},
            "weighted_improvement_per_case": gain, "negative_specificity_loss": specificity_loss,
            "both_arms_contract_complete": quality_ok, "research_rule_met": promote}
