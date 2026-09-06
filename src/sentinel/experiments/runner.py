"""ExperimentRunner: dataset -> adapter -> per-case evaluation -> diagnosis
-> aggregated, reproducibility-stamped ExperimentResult (spec section 21).
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from sentinel.adapters.reference import ReferenceRAGAdapter
from sentinel.core.repro import capture_environment, config_hash, dataset_hash, get_git_commit
from sentinel.core.seed import set_global_seed
from sentinel.diagnosis.engine import DiagnosisEngine
from sentinel.evaluation.aggregate import aggregate_metrics, failure_counts
from sentinel.evaluation.evaluator import CaseEvaluator
from sentinel.schemas.dataset import EvaluationDataset
from sentinel.schemas.evaluation import CaseEvaluation, EvaluationReport
from sentinel.schemas.experiments import ExperimentConfig, ExperimentResult
from sentinel.storage.dataset_store import load_dataset


class ExperimentRunner:
    def __init__(self, diagnose: bool = True) -> None:
        self.diagnose = diagnose
        self._diagnosis_engine = DiagnosisEngine()

    def run(
        self, config: ExperimentConfig, dataset: EvaluationDataset | None = None
    ) -> tuple[ExperimentResult, EvaluationReport]:
        start = time.perf_counter()
        set_global_seed(config.seed)

        dataset = dataset or load_dataset(config.dataset_path)
        evaluator = CaseEvaluator(top_k=config.retrieval.top_k)

        case_results: list[CaseEvaluation] = []
        errors = 0
        for case in dataset.cases:
            try:
                adapter = ReferenceRAGAdapter(
                    retrieval_config=config.retrieval, generation_config=config.generation
                )
                adapter.ingest(case.documents)
                retrieval = adapter.retrieve(case.question)
                generation = adapter.generate(case.question, retrieval)
                case_eval = evaluator.evaluate(case, retrieval, generation)
                if self.diagnose:
                    full_ranking = adapter.full_ranking(case.question)
                    case_eval.failures = self._diagnosis_engine.diagnose(case, case_eval, full_ranking)
                case_results.append(case_eval)
            except Exception as exc:  # noqa: BLE001 - system failures are first-class results
                errors += 1
                case_results.append(
                    CaseEvaluation(
                        case_id=case.id,
                        question=case.question,
                        passed=False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        duration_s = time.perf_counter() - start
        aggregate = aggregate_metrics(case_results)
        counts = failure_counts(case_results)

        report = EvaluationReport(
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            config_name=config.name,
            case_results=case_results,
            aggregate_metrics=aggregate,
            failure_counts=counts,
            total_cases=len(dataset.cases),
            total_errors=errors,
            duration_s=duration_s,
            generated_at=datetime.now(UTC).isoformat(),
            git_commit=get_git_commit(),
            config_hash=config_hash(config),
        )

        payload_for_dataset_hash = {"name": dataset.name, "version": dataset.version, "n_cases": len(dataset.cases)}
        experiment_id = f"exp-{dataset_hash(payload_for_dataset_hash)}-{uuid.uuid4().hex[:8]}"

        result = ExperimentResult(
            experiment_id=experiment_id,
            name=config.name,
            timestamp=report.generated_at,
            git_commit=report.git_commit,
            dataset_version=dataset.version,
            config_hash=report.config_hash,  # type: ignore[arg-type]
            config=config,
            metrics=aggregate,
            duration_s=duration_s,
            environment=capture_environment(),
            num_cases=len(dataset.cases),
            num_failures=sum(counts.values()),
        )
        return result, report
