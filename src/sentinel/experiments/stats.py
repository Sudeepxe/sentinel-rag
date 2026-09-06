"""Statistical analysis for experiment comparisons (spec section 22).

Bootstrap confidence intervals are computed from the ACTUAL per-case
metric values of the two runs being compared — never invented. With small
datasets (Sentinel's golden set is 50 cases) intervals are often wide;
that width is the honest signal that more data or more runs are needed,
and is surfaced rather than hidden.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class BootstrapResult:
    mean_diff: float
    ci_low: float
    ci_high: float
    n_bootstrap: int
    significant: bool  # True iff the 95% CI excludes 0


def paired_bootstrap_diff(
    baseline_values: list[float],
    candidate_values: list[float],
    n_bootstrap: int = 2000,
    seed: int = 1337,
    confidence: float = 0.95,
) -> BootstrapResult:
    if len(baseline_values) != len(candidate_values):
        raise ValueError("paired bootstrap requires equal-length, case-aligned value lists")
    n = len(baseline_values)
    if n == 0:
        return BootstrapResult(mean_diff=0.0, ci_low=0.0, ci_high=0.0, n_bootstrap=0, significant=False)

    # Statistical resampling, not a cryptographic use.
    rng = random.Random(seed)  # nosec B311
    diffs = [c - b for b, c in zip(baseline_values, candidate_values, strict=True)]
    observed_mean_diff = sum(diffs) / n

    resampled_means = []
    for _ in range(n_bootstrap):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        resampled_means.append(sum(sample) / n)
    resampled_means.sort()

    alpha = 1 - confidence
    lo_idx = int((alpha / 2) * n_bootstrap)
    hi_idx = int((1 - alpha / 2) * n_bootstrap) - 1
    ci_low = resampled_means[max(lo_idx, 0)]
    ci_high = resampled_means[min(hi_idx, n_bootstrap - 1)]

    return BootstrapResult(
        mean_diff=observed_mean_diff,
        ci_low=ci_low,
        ci_high=ci_high,
        n_bootstrap=n_bootstrap,
        significant=not (ci_low <= 0 <= ci_high),
    )


def cohens_d(baseline_values: list[float], candidate_values: list[float]) -> float | None:
    n = len(baseline_values)
    if n < 2 or n != len(candidate_values):
        return None
    diffs = [c - b for b, c in zip(baseline_values, candidate_values, strict=True)]
    mean = sum(diffs) / n
    variance = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    std = variance**0.5
    if std == 0:
        return None
    return mean / std


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def sample_variance(values: list[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    m = sum(values) / n
    return sum((v - m) ** 2 for v in values) / (n - 1)
