from __future__ import annotations

from dataclasses import dataclass, field

from sentinel.schemas.evaluation import EvaluationReport
from sentinel.schemas.experiments import ExperimentComparison
from sentinel.schemas.repair import RepairProposal


@dataclass
class ReportBundle:
    """Everything a `sentinel report`/`sentinel benchmark` run may have
    produced. Sections with no data are rendered as explicitly
    'not available in this run' rather than omitted silently, so a reader
    never mistakes absence for a zero/negative result.
    """

    evaluation: EvaluationReport
    title: str = "Sentinel-RAG Reliability Report"
    attack_summary: dict | None = None
    repairs: list[RepairProposal] = field(default_factory=list)
    comparison: ExperimentComparison | None = None
    limitations: list[str] = field(default_factory=list)
    reproducibility: dict[str, str] = field(default_factory=dict)
