from __future__ import annotations

from pydantic import BaseModel, Field

from sentinel.schemas.failures import FailureRecord
from sentinel.schemas.generation import GenerationOutput
from sentinel.schemas.retrieval import RetrievalResult


class MetricValue(BaseModel):
    """A single metric value with provenance so reports can distinguish
    mechanically-measured metrics from LLM-judged ones, or mark a metric
    unavailable instead of fabricating it."""

    value: float | None
    method: str = Field(description="e.g. 'mechanical', 'llm_judge', 'unavailable'")
    detail: str = ""


class CaseEvaluation(BaseModel):
    case_id: str
    question: str
    retrieval: RetrievalResult | None = None
    generation: GenerationOutput | None = None
    metrics: dict[str, MetricValue] = Field(default_factory=dict)
    failures: list[FailureRecord] = Field(default_factory=list)
    passed: bool = True
    error: str | None = None


class EvaluationReport(BaseModel):
    dataset_name: str
    dataset_version: str
    config_name: str
    case_results: list[CaseEvaluation]
    aggregate_metrics: dict[str, MetricValue] = Field(default_factory=dict)
    failure_counts: dict[str, int] = Field(default_factory=dict)
    total_cases: int = 0
    total_errors: int = 0
    duration_s: float = 0.0
    generated_at: str = ""
    git_commit: str | None = None
    config_hash: str | None = None
