"""Ablation runner: executes an ordered list of configs against the same
dataset and reports the marginal effect of each added component (spec
section 23), e.g. dense -> +BM25 -> +RRF -> +reranker -> +query rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass

from sentinel.experiments.runner import ExperimentRunner
from sentinel.schemas.dataset import EvaluationDataset
from sentinel.schemas.evaluation import EvaluationReport
from sentinel.schemas.experiments import ExperimentConfig, ExperimentResult


@dataclass
class AblationStage:
    label: str
    config: ExperimentConfig


@dataclass
class AblationStageResult:
    label: str
    result: ExperimentResult
    report: EvaluationReport


def run_ablation(stages: list[AblationStage], dataset: EvaluationDataset) -> list[AblationStageResult]:
    runner = ExperimentRunner()
    outputs = []
    for stage in stages:
        result, report = runner.run(stage.config, dataset=dataset)
        outputs.append(AblationStageResult(label=stage.label, result=result, report=report))
    return outputs


def marginal_deltas(stage_results: list[AblationStageResult], metric: str) -> list[tuple[str, float | None]]:
    deltas: list[tuple[str, float | None]] = []
    prev_value: float | None = None
    for stage in stage_results:
        mv = stage.result.metrics.get(metric)
        value = mv.value if mv else None
        delta = (value - prev_value) if (value is not None and prev_value is not None) else None
        deltas.append((stage.label, delta))
        if value is not None:
            prev_value = value
    return deltas
