from __future__ import annotations

from pydantic import BaseModel, Field

from sentinel.schemas.experiments import ExperimentConfig
from sentinel.schemas.failures import FailureType


class RepairProposal(BaseModel):
    repair_id: str
    failure_type: FailureType
    proposed_change: str
    rationale: str
    expected_effect: str
    risk: str = Field(description="low | medium | high, plus a one-line reason")
    experiment_config: ExperimentConfig


class AcceptanceCriteria(BaseModel):
    min_relative_improvement: dict[str, float] = Field(
        default_factory=lambda: {"recall_at_5": 0.05},
        description="metric -> minimum required relative improvement to accept the repair",
    )
    max_latency_regression_pct: float = 0.15
    forbid_regression_metrics: list[str] = Field(
        default_factory=lambda: ["answer_relevance", "attack_success_rate"]
    )


class RepairDecision(BaseModel):
    repair_id: str
    accepted: bool
    reasons: list[str]
    baseline_experiment_id: str
    candidate_experiment_id: str
