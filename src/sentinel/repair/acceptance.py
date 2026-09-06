"""Accept/reject a repair candidate from a real baseline-vs-candidate
experiment comparison (spec section 20). Thresholds are configurable, not
hard-coded magic numbers — see AcceptanceCriteria and
configs/experiments/*.yaml `acceptance` blocks.
"""

from __future__ import annotations

from sentinel.schemas.experiments import ExperimentResult
from sentinel.schemas.repair import AcceptanceCriteria, RepairDecision

# Metrics parameterized by top_k (recall_at_5, recall_at_3, ...): if the
# exact configured key isn't present (because the repair's top_k differs
# from the acceptance config's assumed k), fall back to whatever
# same-family "_at_<k>" metric both runs actually produced.
_K_PARAMETERIZED_PREFIXES = ("recall_at_", "precision_at_", "hit_rate_at_", "ndcg_at_")


def _resolve_metric_key(metric: str, baseline: ExperimentResult, candidate: ExperimentResult) -> tuple[str, str]:
    """Resolve possibly-different-k metric names independently in each run.

    A repair that changes top_k (e.g. 1 -> 2) intentionally moves the
    operating point, so "recall_at_1" (baseline) vs "recall_at_2"
    (candidate) IS the correct comparison — it answers "did recall at the
    k we actually serve now improve", not an apples-to-apples same-k
    comparison. Falls back to the literal metric name in each run if no
    "_at_<k>" sibling is found.
    """
    if metric in baseline.metrics and metric in candidate.metrics:
        return metric, metric
    prefix = next((p for p in _K_PARAMETERIZED_PREFIXES if metric.startswith(p)), None)
    if prefix is None:
        return metric, metric
    base_key = next((k for k in baseline.metrics if k.startswith(prefix)), metric)
    cand_key = next((k for k in candidate.metrics if k.startswith(prefix)), metric)
    return base_key, cand_key


def evaluate_acceptance(
    repair_id: str,
    baseline: ExperimentResult,
    candidate: ExperimentResult,
    criteria: AcceptanceCriteria,
) -> RepairDecision:
    reasons: list[str] = []
    accepted = True

    for metric, min_rel_improvement in criteria.min_relative_improvement.items():
        base_key, cand_key = _resolve_metric_key(metric, baseline, candidate)
        base_mv = baseline.metrics.get(base_key)
        cand_mv = candidate.metrics.get(cand_key)
        if base_mv is None or cand_mv is None or base_mv.value is None or cand_mv.value is None:
            accepted = False
            reasons.append(
                f"REJECT: metric {metric!r} (resolved: baseline={base_key!r}, candidate={cand_key!r}) "
                "unavailable in baseline or candidate"
            )
            continue
        metric = f"{base_key}->{cand_key}" if base_key != cand_key else base_key
        if base_mv.value == 0:
            rel_improvement = float("inf") if cand_mv.value > 0 else 0.0
        else:
            rel_improvement = (cand_mv.value - base_mv.value) / abs(base_mv.value)
        if rel_improvement >= min_rel_improvement:
            reasons.append(
                f"PASS: {metric} improved {rel_improvement:+.1%} (required >= {min_rel_improvement:+.1%})"
            )
        else:
            accepted = False
            reasons.append(
                f"REJECT: {metric} improved only {rel_improvement:+.1%} "
                f"(required >= {min_rel_improvement:+.1%})"
            )

    base_latency = baseline.metrics.get("latency_ms")
    cand_latency = candidate.metrics.get("latency_ms")
    if base_latency and cand_latency and base_latency.value and cand_latency.value:
        latency_regression = (cand_latency.value - base_latency.value) / base_latency.value
        if latency_regression > criteria.max_latency_regression_pct:
            accepted = False
            reasons.append(
                f"REJECT: latency regressed {latency_regression:+.1%} "
                f"(max allowed {criteria.max_latency_regression_pct:+.1%})"
            )
        else:
            reasons.append(
                f"PASS: latency changed {latency_regression:+.1%} "
                f"(max allowed {criteria.max_latency_regression_pct:+.1%})"
            )

    for metric in criteria.forbid_regression_metrics:
        base_mv = baseline.metrics.get(metric)
        cand_mv = candidate.metrics.get(metric)
        if not base_mv or not cand_mv or base_mv.value is None or cand_mv.value is None:
            continue
        if cand_mv.value < base_mv.value - 1e-9:
            accepted = False
            reasons.append(f"REJECT: forbidden regression on {metric} ({base_mv.value:.3f} -> {cand_mv.value:.3f})")
        else:
            reasons.append(f"PASS: no regression on {metric} ({base_mv.value:.3f} -> {cand_mv.value:.3f})")

    return RepairDecision(
        repair_id=repair_id,
        accepted=accepted,
        reasons=reasons,
        baseline_experiment_id=baseline.experiment_id,
        candidate_experiment_id=candidate.experiment_id,
    )
