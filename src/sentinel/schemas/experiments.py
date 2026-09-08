from __future__ import annotations

from pydantic import BaseModel, Field

from sentinel.schemas.evaluation import MetricValue


class RetrievalConfig(BaseModel):
    strategy: str = Field(default="hybrid_rrf", description="dense | bm25 | hybrid_rrf")
    top_k: int = 5
    chunk_size: int = 400
    chunk_overlap: int = 50
    use_mmr: bool = False
    mmr_lambda: float = 0.5
    use_reranker: bool = False
    rerank_top_n: int = 20
    query_rewrite: str = Field(default="none", description="none | expansion | hyde | decompose | keyword")
    freshness_policy: str = Field(default="no-preference")
    metadata_filter: dict[str, str] = Field(
        default_factory=dict,
        description="Exact-match filter applied to Chunk.metadata before scoring, e.g. "
        "{'source': 'policy-docs'}. Empty (default) means no filtering.",
    )


class GenerationConfig(BaseModel):
    provider: str = "deterministic_local"
    model: str = "sentinel-deterministic-v1"
    temperature: float = 0.0
    max_context_chunks: int = 5
    refuse_below_evidence_score: float = 0.15


class ExperimentConfig(BaseModel):
    name: str
    description: str = ""
    dataset_path: str
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    seed: int = 1337


class EnvironmentInfo(BaseModel):
    python_version: str
    platform: str
    sentinel_version: str
    packages: dict[str, str] = Field(default_factory=dict)


class ExperimentResult(BaseModel):
    experiment_id: str
    name: str
    timestamp: str
    git_commit: str | None
    dataset_version: str
    config_hash: str
    config: ExperimentConfig
    metrics: dict[str, MetricValue]
    duration_s: float
    environment: EnvironmentInfo
    num_cases: int
    num_failures: int


class ComparisonMetric(BaseModel):
    metric: str
    baseline: float | None
    candidate: float | None
    absolute_diff: float | None
    relative_diff_pct: float | None
    ci_low: float | None = None
    ci_high: float | None = None
    n_bootstrap: int = 0
    significant: bool | None = None


class ExperimentComparison(BaseModel):
    baseline_id: str
    candidate_id: str
    metrics: list[ComparisonMetric]
    notes: list[str] = Field(default_factory=list)
