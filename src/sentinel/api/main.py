"""Optional FastAPI service exposing the same operations as the CLI over
HTTP. The CLI remains the primary interface (spec section 27); this app
is a thin wrapper around the same `sentinel.*` functions the CLI calls,
so there is exactly one implementation of every operation.

Run with: `uvicorn sentinel.api.main:app --reload` or `make serve`.
Intended for local/trusted-network use — see docs/security/threat-model.md
("Out of scope for v1") regarding public exposure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from sentinel.attacks.generator import generate_attack_suite
from sentinel.attacks.runner import AttackRunner
from sentinel.experiments.runner import ExperimentRunner
from sentinel.repair.engine import RepairEngine
from sentinel.schemas.attacks import AttackClass
from sentinel.schemas.experiments import ExperimentConfig
from sentinel.storage.dataset_store import DatasetValidationError, load_dataset
from sentinel.storage.experiment_store import (
    list_experiment_results,
    load_experiment_result,
    save_experiment_result,
)

app = FastAPI(
    title="Sentinel-RAG API",
    version="1.0.0",
    description="Reliability infrastructure for RAG systems — HTTP surface over the sentinel CLI operations.",
)


class DatasetValidateRequest(BaseModel):
    path: str


class EvaluationRequest(BaseModel):
    config_path: str
    dataset_path: str | None = None


class AttackRequest(BaseModel):
    dataset_path: str
    attack_classes: list[str] | None = None
    provider: str = "deterministic_local"
    limit_cases: int = 20


class DiagnoseRequest(BaseModel):
    config_path: str
    dataset_path: str | None = None


class RepairSuggestRequest(BaseModel):
    config_path: str
    dataset_path: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/datasets")
def validate_dataset(req: DatasetValidateRequest) -> dict[str, Any]:
    try:
        dataset = load_dataset(req.path)
    except (DatasetValidationError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "valid": True,
        "name": dataset.name,
        "version": dataset.version,
        "cases": len(dataset.cases),
        "categories": dataset.category_counts(),
    }


@app.post("/evaluations")
def create_evaluation(req: EvaluationRequest) -> dict[str, Any]:
    try:
        config = ExperimentConfig.model_validate_json(Path(req.config_path).read_text()) if req.config_path.endswith(".json") else None
    except Exception:  # noqa: BLE001
        config = None
    if config is None:
        import yaml

        config = ExperimentConfig.model_validate(yaml.safe_load(Path(req.config_path).read_text()))
    if req.dataset_path:
        config.dataset_path = req.dataset_path

    runner = ExperimentRunner()
    result, report = runner.run(config)
    save_experiment_result(result)
    return {
        "experiment_id": result.experiment_id,
        "metrics": {k: v.value for k, v in result.metrics.items()},
        "failure_counts": report.failure_counts,
        "num_errors": report.total_errors,
    }


@app.get("/evaluations/{experiment_id}")
def get_evaluation(experiment_id: str) -> dict[str, Any]:
    path = Path("experiments/results") / f"{experiment_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="experiment result not found")
    result = load_experiment_result(path)
    return result.model_dump(mode="json")


@app.post("/experiments")
def create_experiment(req: EvaluationRequest) -> dict[str, Any]:
    return create_evaluation(req)


@app.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> dict[str, Any]:
    return get_evaluation(experiment_id)


@app.get("/experiments")
def list_experiments() -> dict[str, Any]:
    return {"experiment_ids": [p.stem for p in list_experiment_results()]}


@app.post("/attacks")
def run_attacks(req: AttackRequest) -> dict[str, Any]:
    dataset = load_dataset(req.dataset_path)
    base_cases = [c for c in dataset.cases if c.documents][: req.limit_cases]
    classes = [AttackClass(c) for c in req.attack_classes] if req.attack_classes else None
    attacks = generate_attack_suite(base_cases, classes)

    from sentinel.schemas.experiments import GenerationConfig

    runner = AttackRunner(generation_config=GenerationConfig(provider=req.provider))
    report = runner.run_suite(attacks)
    return {
        "n_attacks": len(attacks),
        "attack_success_rate": report.attack_success_rate,
        "safe_rate": report.safe_rate,
        "partial_rate": report.partial_rate,
        "unknown_rate": report.unknown_rate,
        "by_attack_class": report.by_attack_class,
        "note": report.note,
    }


@app.post("/diagnose")
def diagnose(req: DiagnoseRequest) -> dict[str, Any]:
    import yaml

    config = ExperimentConfig.model_validate(yaml.safe_load(Path(req.config_path).read_text()))
    if req.dataset_path:
        config.dataset_path = req.dataset_path
    runner = ExperimentRunner(diagnose=True)
    _, report = runner.run(config)
    failures = [f.model_dump(mode="json") for c in report.case_results for f in c.failures]
    return {"failures": failures}


@app.post("/repair")
def repair_suggest(req: RepairSuggestRequest) -> dict[str, Any]:
    import yaml

    config = ExperimentConfig.model_validate(yaml.safe_load(Path(req.config_path).read_text()))
    if req.dataset_path:
        config.dataset_path = req.dataset_path
    runner = ExperimentRunner(diagnose=True)
    _, report = runner.run(config)
    all_failures = [f for c in report.case_results for f in c.failures]
    proposals = RepairEngine().suggest(all_failures, config)
    return {"proposals": [p.model_dump(mode="json") for p in proposals]}


@app.get("/reports/{experiment_id}")
def get_report(experiment_id: str) -> dict[str, Any]:
    md_path = Path("reports") / f"{experiment_id}.md"
    if not md_path.exists():
        raise HTTPException(
            status_code=404,
            detail="report not found; generate with `sentinel report generate --config ... --out reports/" + experiment_id + "`",
        )
    return {"markdown": md_path.read_text()}
