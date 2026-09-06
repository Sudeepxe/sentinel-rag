"""Controlled repair loop: diagnose -> propose -> run candidate -> accept/reject."""

from pathlib import Path

from sentinel.experiments.runner import ExperimentRunner
from sentinel.repair.acceptance import evaluate_acceptance
from sentinel.repair.engine import RepairEngine
from sentinel.schemas.experiments import ExperimentConfig, GenerationConfig, RetrievalConfig
from sentinel.schemas.repair import AcceptanceCriteria

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_hybrid_plus_topk_repair_is_accepted_over_bad_baseline():
    bad_config = ExperimentConfig(
        name="bad",
        dataset_path=str(FIXTURES / "repair_demo_dataset.json"),
        retrieval=RetrievalConfig(strategy="dense", top_k=1, chunk_size=1200, chunk_overlap=0),
        generation=GenerationConfig(max_context_chunks=1),
    )
    runner = ExperimentRunner(diagnose=True)
    baseline_result, baseline_report = runner.run(bad_config)
    assert baseline_report.failure_counts  # the bad config must actually fail something

    all_failures = [f for c in baseline_report.case_results for f in c.failures]
    proposals = RepairEngine().suggest(all_failures, bad_config)
    assert proposals

    # The combined fix (hybrid + wider top_k) should look like the good baseline.
    good_config = bad_config.model_copy(deep=True)
    good_config.retrieval = RetrievalConfig(strategy="hybrid_rrf", top_k=5)
    good_config.generation = GenerationConfig(max_context_chunks=5)
    candidate_result, _ = runner.run(good_config)

    # Under the DEFAULT (strict) acceptance criteria, this repair is
    # honestly REJECTED: it improves recall by +100% but also regresses
    # answer_relevance slightly (more context chunks dilute the extractive
    # generator's sentence selection), and default criteria forbid any
    # answer_relevance regression. This is real measured behavior, not a
    # bug — it demonstrates why the acceptance gate exists at all.
    strict_decision = evaluate_acceptance(
        "manual-combined-fix", baseline_result, candidate_result, AcceptanceCriteria()
    )
    assert strict_decision.accepted is False
    assert any("answer_relevance" in r and "REJECT" in r for r in strict_decision.reasons)

    # A team that cares more about recall than relevance can configure
    # looser criteria (spec section 20: thresholds must be configurable)
    # and get an accepted decision on the SAME experiment pair.
    # max_latency_regression_pct is set generously here: both configs run
    # in sub-millisecond wall-clock time against a 1-case dataset, where
    # timing is dominated by measurement jitter, not real cost — this test
    # is about metric-based acceptance, not latency precision.
    lenient_criteria = AcceptanceCriteria(
        min_relative_improvement={"recall_at_5": 0.05},
        max_latency_regression_pct=5.0,
        forbid_regression_metrics=["citation_precision"],
    )
    lenient_decision = evaluate_acceptance(
        "manual-combined-fix", baseline_result, candidate_result, lenient_criteria
    )
    assert lenient_decision.accepted is True


def test_partial_repair_that_does_not_fix_the_root_cause_is_rejected():
    """A repair that changes strategy but keeps top_k=1 should NOT fix a
    rank-4 miss and the acceptance gate must honestly reject it."""
    bad_config = ExperimentConfig(
        name="bad",
        dataset_path=str(FIXTURES / "repair_demo_dataset.json"),
        retrieval=RetrievalConfig(strategy="dense", top_k=1, chunk_size=1200, chunk_overlap=0),
        generation=GenerationConfig(max_context_chunks=1),
    )
    runner = ExperimentRunner(diagnose=False)
    baseline_result, _ = runner.run(bad_config)

    partial_fix = bad_config.model_copy(deep=True)
    partial_fix.retrieval.strategy = "hybrid_rrf"  # top_k still 1
    candidate_result, _ = runner.run(partial_fix)

    decision = evaluate_acceptance("partial-fix", baseline_result, candidate_result, AcceptanceCriteria())
    assert decision.accepted is False
