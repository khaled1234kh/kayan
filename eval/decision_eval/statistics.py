"""Prespecified uncertainty statistics for paired, clustered evaluations."""
from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Sequence


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("empty sample")
    position = (len(ordered) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total < 1 or not 0 <= successes <= total:
        raise ValueError("invalid binomial inputs")
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def paired_bootstrap(
    differences: Sequence[float],
    *,
    replicates: int = 5000,
    seed: int = 20261123,
    cluster: Sequence[str] | None = None,
) -> dict[str, object]:
    """Paired mean difference with percentile 95% CI.

    When ``cluster`` is supplied, whole scenario families are resampled so that
    repeated cases from one family do not masquerade as independent draws.
    """
    if not differences:
        raise ValueError("no paired differences")
    if cluster is not None and len(cluster) != len(differences):
        raise ValueError("cluster and differences must be equal length")
    rng = random.Random(seed)
    n = len(differences)
    groups: list[list[int]] = []
    if cluster is None:
        groups = [[i] for i in range(n)]
    else:
        buckets: dict[str, list[int]] = defaultdict(list)
        for index, key in enumerate(cluster):
            buckets[key].append(index)
        groups = [buckets[key] for key in sorted(buckets)]
    estimates = []
    for _ in range(replicates):
        sampled_groups = [groups[rng.randrange(len(groups))] for _ in groups]
        sample = [differences[i] for group in sampled_groups for i in group]
        estimates.append(mean(sample))
    point = mean(differences)
    result = {
        "estimate": round(point, 6),
        "ci95": [round(percentile(estimates, 0.025), 6), round(percentile(estimates, 0.975), 6)],
        "replicates": replicates,
        "seed": seed,
        "n": n,
        "clusters": len(groups) if cluster is not None else None,
        "unit": "scenario family" if cluster is not None else "case",
    }
    return result


def mcnemar_exact(pass_a: Sequence[bool], pass_b: Sequence[bool]) -> dict[str, object]:
    """Two-sided exact McNemar test on paired pass/fail outcomes."""
    if len(pass_a) != len(pass_b):
        raise ValueError("paired vectors must be equal length")
    b = sum(a and not other for a, other in zip(pass_a, pass_b, strict=True))
    c = sum(other and not a for a, other in zip(pass_a, pass_b, strict=True))
    n = b + c
    if n == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(n, i) for i in range(min(b, c) + 1))
        p_value = min(1.0, 2 * tail / (2 ** n))
    return {
        "b_only_a": b, "c_only_b": c, "discordant": n,
        "p_two_sided": round(p_value, 6),
        "note": "Exact binomial. Ties are excluded. Repeats are not independent cases.",
    }


def judge_agreement(
    judge_binary: Sequence[bool], reference_binary: Sequence[bool]
) -> dict[str, object]:
    """Raw agreement with Cohen's kappa for two binary raters."""
    if len(judge_binary) != len(reference_binary):
        raise ValueError("raters must cover the same items")
    n = len(judge_binary)
    if n == 0:
        raise ValueError("no items")
    a1 = sum(judge_binary)
    a2 = sum(reference_binary)
    observed = sum(j == r for j, r in zip(judge_binary, reference_binary, strict=True)) / n
    expected = (a1 / n) * (a2 / n) + (1 - a1 / n) * (1 - a2 / n)
    kappa = (observed - expected) / (1 - expected) if expected < 1 else None
    return {
        "n": n,
        "raw_agreement": round(observed, 6),
        "expected_agreement": round(expected, 6),
        "cohens_kappa": None if kappa is None else round(kappa, 6),
        "judge_positive_rate": round(a1 / n, 6),
        "reference_positive_rate": round(a2 / n, 6),
        "prevalence_bias": round((a1 - a2) / n, 6),
    }
