from __future__ import annotations

import json
from pathlib import Path

from sentinel.schemas.experiments import ExperimentResult

DEFAULT_RESULTS_DIR = Path("experiments/results")


def save_experiment_result(result: ExperimentResult, results_dir: Path = DEFAULT_RESULTS_DIR) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / f"{result.experiment_id}.json"
    out_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2) + "\n")
    return out_path


def load_experiment_result(path: str | Path) -> ExperimentResult:
    path = Path(path)
    return ExperimentResult.model_validate(json.loads(path.read_text()))


def list_experiment_results(results_dir: Path = DEFAULT_RESULTS_DIR) -> list[Path]:
    if not results_dir.exists():
        return []
    return sorted(results_dir.glob("*.json"))
