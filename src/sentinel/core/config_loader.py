from __future__ import annotations

from pathlib import Path

import yaml

from sentinel.schemas.experiments import ExperimentConfig


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    payload = yaml.safe_load(path.read_text()) or {}
    return ExperimentConfig.model_validate(payload)
