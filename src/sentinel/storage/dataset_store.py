from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from sentinel.schemas.dataset import EvaluationDataset


class DatasetValidationError(Exception):
    pass


def load_dataset(path: str | Path) -> EvaluationDataset:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"dataset not found: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise DatasetValidationError(f"{path}: invalid JSON ({exc})") from exc
    try:
        return EvaluationDataset.model_validate(payload)
    except ValidationError as exc:
        raise DatasetValidationError(f"{path}: schema validation failed:\n{exc}") from exc


def save_dataset(dataset: EvaluationDataset, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataset.model_dump(mode="json"), indent=2, sort_keys=False) + "\n")
