"""Aggregate per-case metrics into a dataset-level report.

Metrics with no numeric values across all cases (all None/unavailable) are
reported as unavailable rather than silently dropped or defaulted to 0 —
callers must be able to tell "0.0 measured" from "could not measure".
"""

from __future__ import annotations

from collections import defaultdict

from sentinel.schemas.evaluation import CaseEvaluation, MetricValue


def aggregate_metrics(case_results: list[CaseEvaluation]) -> dict[str, MetricValue]:
    by_metric: dict[str, list[float]] = defaultdict(list)
    method_by_metric: dict[str, str] = {}
    for case in case_results:
        for name, mv in case.metrics.items():
            method_by_metric[name] = mv.method
            if mv.value is not None:
                by_metric[name].append(mv.value)

    aggregated: dict[str, MetricValue] = {}
    all_metric_names = {name for case in case_results for name in case.metrics}
    for name in sorted(all_metric_names):
        values = by_metric.get(name, [])
        if not values:
            aggregated[name] = MetricValue(value=None, method="unavailable", detail="no cases produced a value")
            continue
        mean_value = sum(values) / len(values)
        aggregated[name] = MetricValue(
            value=mean_value,
            method=method_by_metric.get(name, "mechanical"),
            detail=f"mean over {len(values)}/{len(case_results)} cases",
        )
    return aggregated


def failure_counts(case_results: list[CaseEvaluation]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for case in case_results:
        for failure in case.failures:
            counts[failure.primary.value] += 1
    return dict(counts)
