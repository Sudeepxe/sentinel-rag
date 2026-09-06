"""Sentinel-RAG CLI. `sentinel --help` for the full command tree.

Every command supports `--format json` for machine-readable/CI output and
returns a non-zero exit code on failure so it composes in shell pipelines
and GitHub Actions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from sentinel.adapters.reference import ReferenceRAGAdapter
from sentinel.attacks.generator import generate_attack_suite
from sentinel.attacks.runner import AttackRunner
from sentinel.core.config_loader import load_experiment_config
from sentinel.core.repro import capture_environment, get_git_commit, get_git_dirty
from sentinel.diagnosis.engine import DiagnosisEngine
from sentinel.evaluation.evaluator import CaseEvaluator
from sentinel.experiments.ablation import AblationStage, AblationStageResult, marginal_deltas, run_ablation
from sentinel.experiments.comparison import compare_experiments
from sentinel.experiments.runner import ExperimentRunner
from sentinel.repair.acceptance import evaluate_acceptance
from sentinel.repair.engine import RepairEngine
from sentinel.reporting.bundle import ReportBundle
from sentinel.reporting.render import render_html, render_json, render_markdown
from sentinel.schemas.attacks import AttackClass
from sentinel.schemas.repair import AcceptanceCriteria
from sentinel.storage.dataset_store import DatasetValidationError, load_dataset
from sentinel.storage.experiment_store import load_experiment_result, save_experiment_result

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Sentinel-RAG: reliability infrastructure for RAG systems.")
dataset_app = typer.Typer(no_args_is_help=True, help="Dataset validation and inspection.")
attack_app = typer.Typer(no_args_is_help=True, help="Adversarial test generation and execution.")
experiment_app = typer.Typer(no_args_is_help=True, help="Reproducible experiment runs.")
repair_app = typer.Typer(no_args_is_help=True, help="Failure-driven repair proposals.")
report_app = typer.Typer(no_args_is_help=True, help="Report generation.")
app.add_typer(dataset_app, name="dataset")
app.add_typer(attack_app, name="attack")
app.add_typer(experiment_app, name="experiment")
app.add_typer(repair_app, name="repair")
app.add_typer(report_app, name="report")

console = Console()
err_console = Console(stderr=True)

FormatOpt = Annotated[str, typer.Option("--format", help="text | json")]


def _emit(payload: dict, fmt: str, human_renderer) -> None:
    if fmt == "json":
        print(json.dumps(payload, indent=2, default=str))
    else:
        human_renderer()


@app.command()
def init(directory: Annotated[Path, typer.Argument()] = Path(".")) -> None:
    """Scaffold a new Sentinel-RAG workspace (configs/, datasets/ dirs) in DIRECTORY."""
    for sub in ("configs/experiments", "configs/attacks", "datasets/golden", "reports", "experiments/results"):
        (directory / sub).mkdir(parents=True, exist_ok=True)
    console.print(f"[green]Initialized Sentinel-RAG workspace at {directory.resolve()}[/green]")


@dataset_app.command("validate")
def dataset_validate(path: Path, fmt: FormatOpt = "text") -> None:
    """Validate a dataset file against the EvaluationDataset schema."""
    try:
        dataset = load_dataset(path)
    except (DatasetValidationError, FileNotFoundError) as exc:
        error_message = str(exc)
        _emit(
            {"valid": False, "error": error_message},
            fmt,
            lambda: err_console.print(f"[red]INVALID[/red]: {error_message}"),
        )
        raise typer.Exit(1) from exc

    payload = {"valid": True, "name": dataset.name, "version": dataset.version, "cases": len(dataset.cases), "categories": dataset.category_counts()}

    def _human() -> None:
        console.print(f"[green]VALID[/green]: {dataset.name} v{dataset.version} — {len(dataset.cases)} cases")
        table = Table(title="Cases per category")
        table.add_column("category")
        table.add_column("count", justify="right")
        for cat, count in sorted(dataset.category_counts().items()):
            table.add_row(cat, str(count))
        console.print(table)

    _emit(payload, fmt, _human)


@dataset_app.command("inspect")
def dataset_inspect(path: Path, case_id: Annotated[str | None, typer.Option()] = None, fmt: FormatOpt = "text") -> None:
    """Show details for a dataset, or one case within it."""
    dataset = load_dataset(path)
    if case_id:
        case = next((c for c in dataset.cases if c.id == case_id), None)
        if case is None:
            err_console.print(f"[red]case not found: {case_id}[/red]")
            raise typer.Exit(1)
        _emit(case.model_dump(mode="json"), fmt, lambda: console.print_json(case.model_dump_json()))
        return
    _emit(
        {"name": dataset.name, "version": dataset.version, "cases": [c.id for c in dataset.cases]},
        fmt,
        lambda: console.print(f"{dataset.name} v{dataset.version}: {[c.id for c in dataset.cases]}"),
    )


@app.command()
def evaluate(
    config: Annotated[Path, typer.Option("--config")],
    dataset: Annotated[Path | None, typer.Option("--dataset")] = None,
    fmt: FormatOpt = "text",
    save: Annotated[bool, typer.Option(help="Persist result under experiments/results/")] = True,
) -> None:
    """Run the full retrieval -> generation -> evaluation -> diagnosis loop over a dataset."""
    cfg = load_experiment_config(config)
    if dataset:
        cfg.dataset_path = str(dataset)
    runner = ExperimentRunner()
    result, report = runner.run(cfg)
    if save:
        save_experiment_result(result)

    def _human() -> None:
        console.print(f"[bold]{result.name}[/bold] — {result.experiment_id}")
        console.print(f"commit={result.git_commit} config_hash={result.config_hash} dataset={result.dataset_version}")
        table = Table(title="Aggregate metrics")
        table.add_column("metric")
        table.add_column("value", justify="right")
        table.add_column("method")
        for name, mv in sorted(result.metrics.items()):
            table.add_row(name, f"{mv.value:.4f}" if mv.value is not None else "unavailable", mv.method)
        console.print(table)
        if report.failure_counts:
            console.print(f"[yellow]Failures diagnosed:[/yellow] {report.failure_counts}")
        if report.total_errors:
            console.print(f"[red]{report.total_errors} case(s) errored[/red]")

    _emit(
        {"experiment_id": result.experiment_id, "metrics": {k: v.value for k, v in result.metrics.items()}, "failure_counts": report.failure_counts, "errors": report.total_errors},
        fmt,
        _human,
    )
    if report.total_errors:
        raise typer.Exit(2)


@attack_app.command("generate")
def attack_generate(
    dataset: Annotated[Path, typer.Option("--dataset")],
    out: Annotated[Path, typer.Option("--out")],
    classes: Annotated[str | None, typer.Option(help="Comma-separated AttackClass values, default: all")] = None,
    limit_cases: Annotated[int, typer.Option(help="Max base cases to generate attacks from")] = 20,
) -> None:
    """Generate an adversarial test suite from an existing (answerable) dataset."""
    ds = load_dataset(dataset)
    base_cases = [c for c in ds.cases if c.documents][:limit_cases]
    attack_classes = [AttackClass(c.strip()) for c in classes.split(",")] if classes else None
    attack_cases = generate_attack_suite(base_cases, attack_classes)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([a.model_dump(mode="json") for a in attack_cases], indent=2, default=str))
    console.print(f"Generated {len(attack_cases)} attack cases from {len(base_cases)} base cases -> {out}")


@attack_app.command("run")
def attack_run(
    attacks: Annotated[Path, typer.Option("--attacks")],
    config: Annotated[Path | None, typer.Option("--config")] = None,
    provider: Annotated[str, typer.Option(help="deterministic_local | openai | anthropic")] = "deterministic_local",
    fmt: FormatOpt = "text",
) -> None:
    """Run an adversarial suite and report SAFE/PARTIAL/FAILED/UNKNOWN outcomes."""
    from sentinel.schemas.attacks import AttackCase
    from sentinel.schemas.experiments import GenerationConfig, RetrievalConfig

    raw = json.loads(attacks.read_text())
    attack_cases = [AttackCase.model_validate(a) for a in raw]

    retrieval_cfg = RetrievalConfig()
    if config:
        cfg = load_experiment_config(config)
        retrieval_cfg = cfg.retrieval
    generation_cfg = GenerationConfig(provider=provider)

    runner = AttackRunner(retrieval_config=retrieval_cfg, generation_config=generation_cfg)
    suite_report = runner.run_suite(attack_cases)

    def _human() -> None:
        console.print(f"Ran {len(attack_cases)} attacks against provider={provider!r}")
        table = Table(title="Attack outcomes")
        table.add_column("metric")
        table.add_column("value", justify="right")
        table.add_row("attack_success_rate", f"{suite_report.attack_success_rate:.2%}")
        table.add_row("safe_rate", f"{suite_report.safe_rate:.2%}")
        table.add_row("partial_rate", f"{suite_report.partial_rate:.2%}")
        table.add_row("unknown_rate", f"{suite_report.unknown_rate:.2%}")
        table.add_row("malicious_content_reached_generation_rate", f"{suite_report.malicious_content_reached_generation_rate:.2%}")
        console.print(table)
        console.print(f"[dim]{suite_report.note}[/dim]")

    _emit(
        {
            "attack_success_rate": suite_report.attack_success_rate,
            "safe_rate": suite_report.safe_rate,
            "partial_rate": suite_report.partial_rate,
            "unknown_rate": suite_report.unknown_rate,
            "malicious_content_reached_generation_rate": suite_report.malicious_content_reached_generation_rate,
            "false_positive_rate": suite_report.false_positive_rate,
            "by_attack_class": suite_report.by_attack_class,
            "note": suite_report.note,
        },
        fmt,
        _human,
    )


@app.command()
def diagnose(
    config: Annotated[Path, typer.Option("--config")],
    dataset: Annotated[Path | None, typer.Option("--dataset")] = None,
    case_id: Annotated[str | None, typer.Option("--case-id")] = None,
    fmt: FormatOpt = "text",
) -> None:
    """Run evaluation + diagnosis and print failure records (optionally for one case)."""
    cfg = load_experiment_config(config)
    if dataset:
        cfg.dataset_path = str(dataset)
    runner = ExperimentRunner(diagnose=True)
    _, report = runner.run(cfg)
    cases = [c for c in report.case_results if not case_id or c.case_id == case_id]
    failures = [f.model_dump(mode="json") for c in cases for f in c.failures]

    def _human() -> None:
        if not failures:
            console.print("[green]No failures diagnosed.[/green]")
        for f in failures:
            console.print(f"[bold]{f['case_id']}[/bold]: {f['primary']} (confidence={f['confidence']:.2f})")
            console.print(f"  likely cause: {f['likely_cause']}")
            console.print(f"  evidence: {json.dumps(f['evidence'], default=str)}")

    _emit({"failures": failures}, fmt, _human)


@repair_app.command("suggest")
def repair_suggest(
    config: Annotated[Path, typer.Option("--config")],
    dataset: Annotated[Path | None, typer.Option("--dataset")] = None,
    fmt: FormatOpt = "text",
) -> None:
    """Diagnose failures against CONFIG's dataset and propose config repairs."""
    cfg = load_experiment_config(config)
    if dataset:
        cfg.dataset_path = str(dataset)
    runner = ExperimentRunner(diagnose=True)
    _, report = runner.run(cfg)
    all_failures = [f for c in report.case_results for f in c.failures]
    proposals = RepairEngine().suggest(all_failures, cfg)

    def _human() -> None:
        if not proposals:
            console.print("[green]No repairs proposed (no diagnosed failures, or no catalog entry).[/green]")
        for p in proposals:
            console.print(f"[bold]{p.repair_id}[/bold] (for {p.failure_type.value})")
            console.print(f"  change: {p.proposed_change}")
            console.print(f"  rationale: {p.rationale}")
            console.print(f"  expected effect: {p.expected_effect}")
            console.print(f"  risk: {p.risk}")

    _emit({"proposals": [p.model_dump(mode="json") for p in proposals]}, fmt, _human)


@experiment_app.command("run")
def experiment_run(config: Annotated[Path, typer.Option("--config")], fmt: FormatOpt = "text") -> None:
    """Alias for `sentinel evaluate` that always persists results (spec section 21 naming)."""
    evaluate(config=config, dataset=None, fmt=fmt, save=True)


@experiment_app.command("ablation")
def experiment_ablation(
    stages: Annotated[str, typer.Option(help="Comma-separated experiment config paths, in order")],
    metric: Annotated[str, typer.Option()] = "recall_at_5",
    fmt: FormatOpt = "text",
) -> None:
    """Run an ordered list of configs over the same dataset and report the marginal effect of each."""
    stage_paths = [Path(p.strip()) for p in stages.split(",")]
    stage_configs = [load_experiment_config(p) for p in stage_paths]
    ds = load_dataset(stage_configs[0].dataset_path)
    ablation_stages = [AblationStage(label=cfg.name, config=cfg) for cfg in stage_configs]
    results = run_ablation(ablation_stages, ds)
    deltas = marginal_deltas(results, metric)
    for r in results:
        save_experiment_result(r.result)

    def _human() -> None:
        table = Table(title=f"Ablation: marginal effect on {metric}")
        table.add_column("stage")
        table.add_column("value", justify="right")
        table.add_column("marginal delta", justify="right")
        for stage_result, (label, delta) in zip(results, deltas, strict=True):
            mv = stage_result.result.metrics.get(metric)
            value = f"{mv.value:.4f}" if mv and mv.value is not None else "unavailable"
            table.add_row(label, value, f"{delta:+.4f}" if delta is not None else "n/a")
        console.print(table)

    def _stage_value(stage_result: AblationStageResult) -> float | None:
        mv = stage_result.result.metrics.get(metric)
        return mv.value if mv is not None else None

    _emit(
        {
            "metric": metric,
            "stages": [
                {"label": r.label, "experiment_id": r.result.experiment_id, "value": _stage_value(r)}
                for r in results
            ],
            "marginal_deltas": deltas,
        },
        fmt,
        _human,
    )


@repair_app.command("run")
def repair_run(
    repair_id: Annotated[str, typer.Option("--repair-id")],
    base_config: Annotated[Path, typer.Option("--config")],
    dataset: Annotated[Path | None, typer.Option("--dataset")] = None,
    acceptance_config: Annotated[Path, typer.Option("--acceptance")] = Path("configs/experiments/acceptance_default.yaml"),
    fmt: FormatOpt = "text",
) -> None:
    """Diagnose, propose repairs, pick REPAIR_ID, run baseline vs candidate, and accept/reject."""
    cfg = load_experiment_config(base_config)
    if dataset:
        cfg.dataset_path = str(dataset)
    runner = ExperimentRunner(diagnose=True)
    baseline_result, baseline_report = runner.run(cfg)
    save_experiment_result(baseline_result)

    all_failures = [f for c in baseline_report.case_results for f in c.failures]
    proposals = RepairEngine().suggest(all_failures, cfg)
    proposal = next((p for p in proposals if p.repair_id == repair_id), None)
    if proposal is None:
        available = [p.repair_id for p in proposals]
        err_console.print(f"[red]repair_id {repair_id!r} not found. Available: {available}[/red]")
        raise typer.Exit(1)

    candidate_result, _ = runner.run(proposal.experiment_config)
    save_experiment_result(candidate_result)

    criteria = AcceptanceCriteria.model_validate(yaml.safe_load(acceptance_config.read_text()))
    decision = evaluate_acceptance(repair_id, baseline_result, candidate_result, criteria)

    def _human() -> None:
        console.print(f"[bold]{'ACCEPTED' if decision.accepted else 'REJECTED'}[/bold]: {repair_id}")
        for reason in decision.reasons:
            console.print(f"  - {reason}")

    _emit(decision.model_dump(mode="json"), fmt, _human)
    if not decision.accepted:
        raise typer.Exit(1)


@app.command()
def compare(
    baseline: Annotated[str, typer.Option("--baseline")],
    candidate: Annotated[str, typer.Option("--candidate")],
    fmt: FormatOpt = "text",
) -> None:
    """Compare two saved experiment results by id or path, with bootstrap CIs."""
    base_path = Path(baseline) if Path(baseline).exists() else Path("experiments/results") / f"{baseline}.json"
    cand_path = Path(candidate) if Path(candidate).exists() else Path("experiments/results") / f"{candidate}.json"
    base_result = load_experiment_result(base_path)
    cand_result = load_experiment_result(cand_path)
    comparison = compare_experiments(base_result, cand_result)

    def _human() -> None:
        table = Table(title=f"{base_result.experiment_id} vs {cand_result.experiment_id}")
        table.add_column("metric")
        table.add_column("baseline", justify="right")
        table.add_column("candidate", justify="right")
        table.add_column("rel diff %", justify="right")
        for m in comparison.metrics:
            table.add_row(
                m.metric,
                f"{m.baseline:.4f}" if m.baseline is not None else "n/a",
                f"{m.candidate:.4f}" if m.candidate is not None else "n/a",
                f"{m.relative_diff_pct:+.1f}" if m.relative_diff_pct is not None else "n/a",
            )
        console.print(table)
        for note in comparison.notes:
            console.print(f"[dim]{note}[/dim]")

    _emit(comparison.model_dump(mode="json"), fmt, _human)


@report_app.command("generate")
def report_generate(
    config: Annotated[Path, typer.Option("--config")],
    dataset: Annotated[Path | None, typer.Option("--dataset")] = None,
    out_prefix: Annotated[Path, typer.Option("--out")] = Path("reports/latest"),
) -> None:
    """Run an evaluation and write Markdown/JSON/HTML reports to OUT_PREFIX.{md,json,html}."""
    cfg = load_experiment_config(config)
    if dataset:
        cfg.dataset_path = str(dataset)
    runner = ExperimentRunner()
    result, report = runner.run(cfg)
    save_experiment_result(result)

    bundle = ReportBundle(
        evaluation=report,
        reproducibility={
            "python_version": result.environment.python_version,
            "platform": result.environment.platform,
            "sentinel_version": result.environment.sentinel_version,
            "seed": str(cfg.seed),
            "git_dirty": str(get_git_dirty()),
        },
    )
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".md").write_text(render_markdown(bundle))
    out_prefix.with_suffix(".json").write_text(render_json(bundle))
    out_prefix.with_suffix(".html").write_text(render_html(bundle))
    console.print(f"Wrote {out_prefix}.md, {out_prefix}.json, {out_prefix}.html")


@app.command()
def benchmark(
    config: Annotated[Path, typer.Option("--config")] = Path("configs/experiments/baseline.yaml"),
    out_prefix: Annotated[Path, typer.Option("--out")] = Path("reports/latest"),
) -> None:
    """Run the official local benchmark (baseline config over the golden dataset) and write reports/."""
    report_generate(config=config, dataset=None, out_prefix=out_prefix)


@app.command()
def doctor(fmt: FormatOpt = "text") -> None:
    """Environment sanity check: python/deps/dataset/git status."""
    checks: dict[str, object] = {}
    env = capture_environment()
    checks["python_version"] = env.python_version
    checks["platform"] = env.platform
    checks["git_commit"] = get_git_commit()
    checks["git_dirty"] = get_git_dirty()
    golden_path = Path("datasets/golden/v1.json")
    checks["golden_dataset_present"] = golden_path.exists()
    if golden_path.exists():
        try:
            ds = load_dataset(golden_path)
            checks["golden_dataset_valid"] = True
            checks["golden_dataset_cases"] = len(ds.cases)
        except DatasetValidationError as exc:
            checks["golden_dataset_valid"] = False
            checks["golden_dataset_error"] = str(exc)
    ok = checks.get("golden_dataset_present") and checks.get("golden_dataset_valid", True)

    def _human() -> None:
        for k, v in checks.items():
            console.print(f"{k}: {v}")
        console.print("[green]OK[/green]" if ok else "[red]PROBLEMS FOUND[/red]")

    _emit(checks, fmt, _human)
    if not ok:
        raise typer.Exit(1)


@app.command()
def replay(
    config: Annotated[Path, typer.Option("--config")],
    dataset: Annotated[Path, typer.Option("--dataset")],
    case_id: Annotated[str, typer.Option("--case")],
    fmt: FormatOpt = "text",
) -> None:
    """Reproduce a single case's full retrieval/generation/evaluation trace."""
    cfg = load_experiment_config(config)
    ds = load_dataset(dataset)
    case = next((c for c in ds.cases if c.id == case_id), None)
    if case is None:
        err_console.print(f"[red]case not found: {case_id}[/red]")
        raise typer.Exit(1)

    adapter = ReferenceRAGAdapter(retrieval_config=cfg.retrieval, generation_config=cfg.generation)
    adapter.ingest(case.documents)
    retrieval = adapter.retrieve(case.question)
    generation = adapter.generate(case.question, retrieval)
    case_eval = CaseEvaluator(top_k=cfg.retrieval.top_k).evaluate(case, retrieval, generation)
    case_eval.failures = DiagnosisEngine().diagnose(case, case_eval, adapter.full_ranking(case.question))

    payload = case_eval.model_dump(mode="json")
    payload["reproducibility_note"] = (
        "Deterministic local provider: bit-for-bit reproducible given the same config/dataset/git "
        "commit. Real-LLM providers (openai/anthropic) are NOT guaranteed reproducible even with "
        "temperature=0 due to provider-side nondeterminism."
    )

    def _human() -> None:
        console.print_json(json.dumps(payload, default=str))

    _emit(payload, fmt, _human)


@app.command()
def gate(
    baseline: Annotated[str, typer.Option("--baseline")],
    candidate: Annotated[str, typer.Option("--candidate")],
    thresholds: Annotated[Path, typer.Option("--thresholds")] = Path("configs/experiments/regression_gate.yaml"),
    fmt: FormatOpt = "text",
) -> None:
    """CI regression gate: fail if CANDIDATE regresses beyond configured tolerances vs BASELINE."""
    base_path = Path(baseline) if Path(baseline).exists() else Path("experiments/results") / f"{baseline}.json"
    cand_path = Path(candidate) if Path(candidate).exists() else Path("experiments/results") / f"{candidate}.json"
    base_result = load_experiment_result(base_path)
    cand_result = load_experiment_result(cand_path)
    rules = yaml.safe_load(thresholds.read_text())
    drop_rules = rules.get("max_regression", {})
    rise_rules = rules.get("max_increase", {})

    violations = []
    for metric, max_drop in drop_rules.items():
        base_mv = base_result.metrics.get(metric)
        cand_mv = cand_result.metrics.get(metric)
        if not base_mv or not cand_mv or base_mv.value is None or cand_mv.value is None:
            continue
        drop = base_mv.value - cand_mv.value
        if drop > max_drop:
            violations.append(f"{metric} dropped {drop:.4f} (max allowed {max_drop})")
    for metric, max_rise in rise_rules.items():
        base_mv = base_result.metrics.get(metric)
        cand_mv = cand_result.metrics.get(metric)
        if not base_mv or not cand_mv or base_mv.value is None or cand_mv.value is None:
            continue
        rise = cand_mv.value - base_mv.value
        if rise > max_rise:
            violations.append(f"{metric} rose {rise:.4f} (max allowed increase {max_rise})")

    passed = not violations

    def _human() -> None:
        if passed:
            console.print("[green]GATE PASSED[/green]")
        else:
            console.print("[red]GATE FAILED[/red]")
            for v in violations:
                console.print(f"  - {v}")

    _emit({"passed": passed, "violations": violations}, fmt, _human)
    if not passed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
