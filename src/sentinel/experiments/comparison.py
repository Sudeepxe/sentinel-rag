"""Compare two experiment results with bootstrap confidence intervals
computed from paired per-case metric values (not just aggregate deltas).
"""

from __future__ import annotations

from sentinel.experiments.stats import paired_bootstrap_diff
from sentinel.schemas.evaluation import CaseEvaluation
from sentinel.schemas.experiments import ComparisonMetric, ExperimentComparison, ExperimentResult


def compare_experiments(
    baseline: ExperimentResult,
    candidate: ExperimentResult,
    baseline_cases: list[CaseEvaluation] | None = None,
    candidate_cases: list[CaseEvaluation] | None = None,
) -> ExperimentComparison:
    metrics: list[ComparisonMetric] = []
    notes: list[str] = []

    all_metric_names = sorted(set(baseline.metrics) | set(candidate.metrics))
    paired_available = bool(baseline_cases and candidate_cases)
    if not paired_available:
        notes.append(
            "Per-case results not supplied; confidence intervals are unavailable. "
            "Re-run via `sentinel compare` (not by hand-editing metrics) to get bootstrap CIs."
        )

    case_index = {}
    if paired_available:
        cand_by_id = {c.case_id: c for c in candidate_cases}  # type: ignore[union-attr]
        for base_case in baseline_cases:  # type: ignore[union-attr]
            if base_case.case_id in cand_by_id:
                case_index[base_case.case_id] = (base_case, cand_by_id[base_case.case_id])

    for name in all_metric_names:
        base_mv = baseline.metrics.get(name)
        cand_mv = candidate.metrics.get(name)
        base_val = base_mv.value if base_mv else None
        cand_val = cand_mv.value if cand_mv else None

        abs_diff = (cand_val - base_val) if (base_val is not None and cand_val is not None) else None
        rel_diff = (
            (cand_val - base_val) / abs(base_val) * 100
            if (base_val not in (None, 0) and cand_val is not None)
            else None
        )

        ci_low = ci_high = None
        n_boot = 0
        significant = None
        if paired_available and case_index:
            base_series, cand_series = [], []
            for base_case, cand_case in case_index.values():
                b = base_case.metrics.get(name)
                c = cand_case.metrics.get(name)
                if b and c and b.value is not None and c.value is not None:
                    base_series.append(b.value)
                    cand_series.append(c.value)
            if len(base_series) >= 5:
                boot = paired_bootstrap_diff(base_series, cand_series)
                ci_low, ci_high, n_boot, significant = boot.ci_low, boot.ci_high, boot.n_bootstrap, boot.significant
            elif base_series:
                notes.append(f"{name}: only {len(base_series)} paired cases, skipping bootstrap CI (need >= 5)")

        metrics.append(
            ComparisonMetric(
                metric=name,
                baseline=base_val,
                candidate=cand_val,
                absolute_diff=abs_diff,
                relative_diff_pct=rel_diff,
                ci_low=ci_low,
                ci_high=ci_high,
                n_bootstrap=n_boot,
                significant=significant,
            )
        )

    return ExperimentComparison(
        baseline_id=baseline.experiment_id, candidate_id=candidate.experiment_id, metrics=metrics, notes=notes
    )
