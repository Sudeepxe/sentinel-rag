"""Report rendering: Markdown (canonical), JSON (machine-readable), and a
minimal HTML wrapper around the same content (spec section 36).
"""

from __future__ import annotations

import html
import json

from sentinel.reporting.bundle import ReportBundle
from sentinel.schemas.evaluation import MetricValue

_RETRIEVAL_METRICS = ("recall_at_5", "precision_at_5", "hit_rate_at_5", "mrr", "ndcg_at_5")
_GENERATION_METRICS = ("faithfulness", "answer_relevance")
_CITATION_METRICS = ("citation_precision", "citation_recall")
_SYSTEM_METRICS = ("latency_ms", "total_tokens", "estimated_cost_usd")


def _fmt(mv: MetricValue | None) -> str:
    if mv is None or mv.value is None:
        detail = f" ({mv.detail})" if mv and mv.detail else ""
        return f"unavailable{detail}"
    return f"{mv.value:.4f} [{mv.method}]"


def _metrics_table(metrics: dict[str, MetricValue], keys: tuple[str, ...]) -> str:
    lines = ["| metric | value | method |", "|---|---|---|"]
    for key in keys:
        mv = metrics.get(key)
        if mv is None:
            lines.append(f"| {key} | unavailable | n/a |")
        elif mv.value is None:
            lines.append(f"| {key} | unavailable | {mv.method} |")
        else:
            lines.append(f"| {key} | {mv.value:.4f} | {mv.method} |")
    return "\n".join(lines)


def render_markdown(bundle: ReportBundle) -> str:
    report = bundle.evaluation
    lines: list[str] = []
    lines.append(f"# {bundle.title}")
    lines.append("")
    lines.append(f"Generated: {report.generated_at}  ")
    lines.append(f"Git commit: `{report.git_commit or 'unknown'}`  ")
    lines.append(f"Config hash: `{report.config_hash or 'unknown'}`  ")
    lines.append(f"Config: `{report.config_name}`  ")
    lines.append(f"Dataset: `{report.dataset_name}` v{report.dataset_version} ({report.total_cases} cases)")
    lines.append("")

    lines.append("## Executive Summary")
    passed = sum(1 for c in report.case_results if c.passed and not c.error)
    lines.append(
        f"- {passed}/{report.total_cases} cases evaluated without a system error "
        f"({report.total_errors} system-level errors).\n"
        f"- Evaluated in {report.duration_s:.2f}s.\n"
        f"- {sum(report.failure_counts.values())} case(s) received a diagnosed failure record."
    )
    lines.append("")

    lines.append("## Retrieval Metrics")
    lines.append(_metrics_table(report.aggregate_metrics, _RETRIEVAL_METRICS))
    lines.append("")

    lines.append("## Generation Metrics")
    lines.append(_metrics_table(report.aggregate_metrics, _GENERATION_METRICS))
    lines.append("")

    lines.append("## Citation Metrics")
    lines.append(_metrics_table(report.aggregate_metrics, _CITATION_METRICS))
    lines.append("")

    lines.append("## Refusal Metrics")
    refusal_label = report.aggregate_metrics.get("refusal_label")
    lines.append(f"- refusal_label aggregate (categorical, see per-case breakdown): {_fmt(refusal_label)}")
    lines.append("")

    lines.append("## Security Metrics")
    if bundle.attack_summary:
        for k, v in bundle.attack_summary.items():
            if k in ("results", "by_attack_class", "note"):
                continue
            lines.append(f"- {k}: {v:.4f}" if isinstance(v, float) else f"- {k}: {v}")
        if "note" in bundle.attack_summary:
            lines.append(f"\n> {bundle.attack_summary['note']}")
    else:
        lines.append("Not available in this run — run `sentinel attack run` and pass its summary in.")
    lines.append("")

    lines.append("## Latency / Cost")
    lines.append(_metrics_table(report.aggregate_metrics, _SYSTEM_METRICS))
    lines.append("")

    lines.append("## Failure Taxonomy")
    if report.failure_counts:
        lines.append("| failure type | count |")
        lines.append("|---|---|")
        for ftype, count in sorted(report.failure_counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {ftype} | {count} |")
    else:
        lines.append("No failures diagnosed in this run.")
    lines.append("")

    lines.append("## Root Cause Analysis (worst 5 cases by confidence)")
    diagnosed = [c for c in report.case_results if c.failures]
    diagnosed.sort(key=lambda c: -max(f.confidence for f in c.failures))
    if diagnosed:
        for case in diagnosed[:5]:
            f = max(case.failures, key=lambda x: x.confidence)
            lines.append(
                f"- **{case.case_id}**: primary=`{f.primary.value}` "
                f"(confidence={f.confidence:.2f}) — {f.likely_cause}"
            )
    else:
        lines.append("No diagnosed failures.")
    lines.append("")

    lines.append("## Repair Recommendations")
    if bundle.repairs:
        for r in bundle.repairs:
            lines.append(f"- `{r.repair_id}` for `{r.failure_type.value}`: {r.proposed_change}")
            lines.append(f"  - rationale: {r.rationale}")
            lines.append(f"  - expected effect: {r.expected_effect}")
            lines.append(f"  - risk: {r.risk}")
    else:
        lines.append("No repair proposals attached to this run.")
    lines.append("")

    lines.append("## Experiment Comparison")
    if bundle.comparison:
        lines.append(f"Baseline: `{bundle.comparison.baseline_id}` vs Candidate: `{bundle.comparison.candidate_id}`")
        lines.append("")
        lines.append("| metric | baseline | candidate | abs diff | rel diff % | 95% CI | significant |")
        lines.append("|---|---|---|---|---|---|---|")
        for m in bundle.comparison.metrics:
            ci = f"[{m.ci_low:.3f}, {m.ci_high:.3f}] (n={m.n_bootstrap})" if m.ci_low is not None else "n/a"
            lines.append(
                f"| {m.metric} | {m.baseline if m.baseline is not None else 'n/a'} | "
                f"{m.candidate if m.candidate is not None else 'n/a'} | "
                f"{m.absolute_diff if m.absolute_diff is not None else 'n/a'} | "
                f"{m.relative_diff_pct if m.relative_diff_pct is not None else 'n/a'} | {ci} | "
                f"{m.significant if m.significant is not None else 'n/a'} |"
            )
        for note in bundle.comparison.notes:
            lines.append(f"\n> {note}")
    else:
        lines.append("No baseline/candidate comparison attached to this run.")
    lines.append("")

    lines.append("## Limitations")
    default_limits = [
        "Retrieval-metric ground truth is at document granularity unless a case specifies "
        "`relevant_chunk_ids`; see docs/evaluation/retrieval-metrics.md.",
        "Faithfulness and citation-support checks default to a mechanical lexical-overlap proxy, "
        "not a validated entailment model or LLM judge, unless an LLM judge was explicitly configured.",
        "The deterministic local provider is an extractive baseline, not a language model; "
        "generation-quality numbers from it are a floor, not representative of a real LLM.",
    ]
    for item in default_limits + bundle.limitations:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Reproducibility")
    lines.append(f"- git_commit: `{report.git_commit or 'unknown'}`")
    lines.append(f"- config_hash: `{report.config_hash or 'unknown'}`")
    lines.append(f"- dataset_version: `{report.dataset_version}`")
    for k, v in bundle.reproducibility.items():
        lines.append(f"- {k}: `{v}`")
    lines.append("- Reproduce with: `sentinel evaluate --config <config.yaml> --dataset <dataset.json>`")
    lines.append("")

    return "\n".join(lines)


def render_json(bundle: ReportBundle) -> str:
    payload = {
        "evaluation": bundle.evaluation.model_dump(mode="json"),
        "attack_summary": bundle.attack_summary,
        "repairs": [r.model_dump(mode="json") for r in bundle.repairs],
        "comparison": bundle.comparison.model_dump(mode="json") if bundle.comparison else None,
        "limitations": bundle.limitations,
        "reproducibility": bundle.reproducibility,
    }
    return json.dumps(payload, indent=2, default=str)


def render_html(bundle: ReportBundle) -> str:
    markdown_text = render_markdown(bundle)
    escaped = html.escape(markdown_text)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(bundle.title)}</title>"
        "<style>body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;"
        "max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.5;color:#1a1a1a}"
        "pre{white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.9rem}"
        "</style></head><body><pre>" + escaped + "</pre></body></html>"
    )
