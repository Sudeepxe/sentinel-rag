"""End-to-end: dataset -> ReferenceRAGAdapter -> evaluation -> diagnosis.

Uses the same smoke dataset fixture the CLI was manually smoke-tested
against during development.
"""

from pathlib import Path

from sentinel.adapters.reference import ReferenceRAGAdapter
from sentinel.diagnosis.engine import DiagnosisEngine
from sentinel.evaluation.evaluator import CaseEvaluator
from sentinel.schemas.experiments import GenerationConfig, RetrievalConfig
from sentinel.storage.dataset_store import load_dataset

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_smoke_dataset_end_to_end():
    dataset = load_dataset(FIXTURES / "smoke_dataset.json")
    evaluator = CaseEvaluator(top_k=5)
    diagnosis = DiagnosisEngine()

    results = []
    for case in dataset.cases:
        adapter = ReferenceRAGAdapter(retrieval_config=RetrievalConfig(), generation_config=GenerationConfig())
        adapter.ingest(case.documents)
        retrieval = adapter.retrieve(case.question)
        generation = adapter.generate(case.question, retrieval)
        case_eval = evaluator.evaluate(case, retrieval, generation)
        case_eval.failures = diagnosis.diagnose(case, case_eval, adapter.full_ranking(case.question))
        results.append(case_eval)

    answerable = next(c for c in results if c.case_id == "smoke-001")
    unanswerable = next(c for c in results if c.case_id == "smoke-002")

    assert answerable.generation.refused is False
    assert answerable.metrics["recall_at_5"].value == 1.0
    assert answerable.metrics["citation_precision"].value == 1.0
    assert answerable.failures == []

    assert unanswerable.generation.refused is True
    assert unanswerable.metrics["refusal_label"].detail == "correct_refusal"


def test_dense_only_low_top_k_causes_measurable_recall_regression():
    """The 'bad config' used in the failure demo (docs/experiments) must
    actually score worse than the recommended baseline on a
    terminology-mismatch case — otherwise the demo would be fabricated."""
    dataset = load_dataset(FIXTURES / "repair_demo_dataset.json")
    case = next(c for c in dataset.cases if c.id == "repair-002")
    evaluator = CaseEvaluator(top_k=1)

    bad_adapter = ReferenceRAGAdapter(
        retrieval_config=RetrievalConfig(strategy="dense", top_k=1, chunk_size=1200, chunk_overlap=0),
        generation_config=GenerationConfig(max_context_chunks=1),
    )
    bad_adapter.ingest(case.documents)
    bad_retrieval = bad_adapter.retrieve(case.question)
    bad_eval = evaluator.evaluate(case, bad_retrieval, bad_adapter.generate(case.question, bad_retrieval))

    good_evaluator = CaseEvaluator(top_k=5)
    good_adapter = ReferenceRAGAdapter(
        retrieval_config=RetrievalConfig(strategy="hybrid_rrf", top_k=5), generation_config=GenerationConfig()
    )
    good_adapter.ingest(case.documents)
    good_retrieval = good_adapter.retrieve(case.question)
    good_eval = good_evaluator.evaluate(case, good_retrieval, good_adapter.generate(case.question, good_retrieval))

    assert bad_eval.metrics["recall_at_1"].value == 0.0
    assert good_eval.metrics["recall_at_5"].value == 1.0
