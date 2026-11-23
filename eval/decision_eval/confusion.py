"""Confusion matrices and classification metrics for canonical decisions."""
from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence

from . import CANONICAL_CLASSES


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def confusion_matrix(
    truth: Sequence[str], predicted: Sequence[str], labels: Sequence[str] = CANONICAL_CLASSES
) -> dict[str, object]:
    """Full and row-normalized matrices. Rows = truth, columns = prediction."""
    if len(truth) != len(predicted):
        raise ValueError("truth and predicted must be equal length")
    index = {label: i for i, label in enumerate(labels)}
    for value in (*truth, *predicted):
        if value not in index:
            raise ValueError(f"Unexpected class {value!r}; expected one of {labels}")
    matrix = [[0 for _ in labels] for _ in labels]
    for t, p in zip(truth, predicted, strict=True):
        matrix[index[t]][index[p]] += 1
    rows = []
    for row in matrix:
        total = sum(row)
        rows.append([round(value / total, 6) if total else None for value in row])
    return {
        "labels": list(labels),
        "matrix": matrix,
        "row_normalized": rows,
        "support": [sum(row) for row in matrix],
        "total": sum(map(sum, matrix)),
    }


def binary_counts(
    truth: Sequence[str], predicted: Sequence[str], positive: str
) -> dict[str, int]:
    """One-vs-rest TP/FP/FN/TN where the positive class is meaningful."""
    tp = sum(t == positive and p == positive for t, p in zip(truth, predicted, strict=True))
    fp = sum(t != positive and p == positive for t, p in zip(truth, predicted, strict=True))
    fn = sum(t == positive and p != positive for t, p in zip(truth, predicted, strict=True))
    tn = len(truth) - tp - fp - fn
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "support": tp + fn}


def prf1(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * tp, 2 * tp + fp + fn) if (tp or fp or fn) else None
    return {
        "precision": None if precision is None else round(precision, 6),
        "recall": None if recall is None else round(recall, 6),
        "f1": None if f1 is None else round(f1, 6),
    }


def classification_report(
    truth: Sequence[str],
    predicted: Sequence[str],
    labels: Sequence[str] = CANONICAL_CLASSES,
) -> dict[str, object]:
    """Per-class, macro/micro/weighted F1 and balanced accuracy.

    Classes with zero support are reported with null per-class metrics but still
    included in macro/weighted aggregation only when a metric is defined. This
    prevents absent Planner abstention rows from being scored as failures.
    """
    cm = confusion_matrix(truth, predicted, labels)
    per_class: dict[str, dict[str, object]] = {}
    for label in labels:
        counts = binary_counts(truth, predicted, label)
        per_class[label] = {
            **counts,
            **prf1(counts["tp"], counts["fp"], counts["fn"]),
        }
    defined = [row for row in per_class.values() if row["f1"] is not None]
    macro_f1 = (round(sum(float(row["f1"]) for row in defined) / len(defined), 6)
                if defined else None)
    total = len(truth)
    correct = sum(cm["matrix"][i][i] for i in range(len(labels)))
    accuracy = _ratio(correct, total)
    recalls = [float(row["recall"]) for row in per_class.values() if row["recall"] is not None]
    balanced = round(sum(recalls) / len(recalls), 6) if recalls else None
    weighted_f1 = None
    if total and defined:
        weighted_f1 = round(sum(
            float(row["f1"]) * int(row["support"]) for row in defined
        ) / total, 6)
    return {
        "confusion": cm,
        "per_class": per_class,
        "accuracy": None if accuracy is None else round(accuracy, 6),
        "macro_f1": macro_f1,
        "micro_f1": None if accuracy is None else round(accuracy, 6),
        "weighted_f1": weighted_f1,
        "balanced_accuracy": balanced,
        "support": total,
        "note": "In single-label multiclass, micro-F1 equals accuracy. Exact case-level pass rate is reported separately.",
    }


def abstention_metrics(truth: Sequence[str], predicted: Sequence[str]) -> dict[str, object]:
    counts = binary_counts(truth, predicted, "abstain")
    result = {"counts": counts, **prf1(counts["tp"], counts["fp"], counts["fn"])}
    result["false_abstention_rate"] = _ratio(counts["fp"], len(truth) - counts["tp"] - counts["tn"])
    result["false_abstention_rate"] = (
        None if result["false_abstention_rate"] is None
        else round(result["false_abstention_rate"], 6)
    )
    result["abstention_coverage"] = _ratio(counts["tp"], counts["support"])
    result["abstention_coverage"] = (
        None if result["abstention_coverage"] is None else round(result["abstention_coverage"], 6)
    )
    return result


def aggregate_reports(reports: Iterable[dict[str, object]], labels: Sequence[str] = CANONICAL_CLASSES) -> dict[str, object]:
    """Pool confusion matrices from per-agent reports into an overall report."""
    matrices = [report["confusion"] for report in reports]
    size = len(labels)
    pooled = [[0 for _ in labels] for _ in labels]
    for matrix in matrices:
        for i in range(size):
            for j in range(size):
                pooled[i][j] += int(matrix["matrix"][i][j])
    truth: list[str] = []
    predicted: list[str] = []
    for i, t in enumerate(labels):
        for j, p in enumerate(labels):
            truth.extend([t] * pooled[i][j])
            predicted.extend([p] * pooled[i][j])
    return classification_report(truth, predicted, labels)


def distinct_error_counts(rows: Iterable[dict[str, int]], keys: Sequence[str]) -> dict[str, int]:
    """Count cases (not occurrences) exhibiting each error category."""
    counter: Counter[str] = Counter()
    for row in rows:
        for key in keys:
            if int(row.get(key, 0)) > 0:
                counter[key] += 1
    return {key: counter[key] for key in keys}
