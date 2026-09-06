"""Per-case evaluation orchestration.

Retrieval relevance granularity: if the case supplies explicit
`relevant_chunk_ids`, matching happens at chunk granularity (needed when a
document has multiple chunks and only a specific one is authoritative,
e.g. conflicting-evidence cases). Otherwise matching happens at DOCUMENT
granularity (retrieved chunk -> its document_id vs relevant_document_ids).
Document granularity is chunking-config-robust: it stays meaningful when
an experiment varies chunk_size/overlap, whereas chunk ids would silently
stop matching. This tradeoff is documented in
docs/evaluation/retrieval-metrics.md.
"""

from __future__ import annotations

from sentinel.evaluation.answer_relevance import lexical_answer_relevance
from sentinel.evaluation.faithfulness import MechanicalFaithfulnessJudge
from sentinel.metrics.citation import (
    check_citations,
    citation_precision,
    citation_recall,
    extract_claims,
)
from sentinel.metrics.refusal import RefusalOutcome
from sentinel.metrics.retrieval import hit_rate_at_k, mrr, ndcg_at_k, precision_at_k, recall_at_k
from sentinel.schemas.dataset import DatasetCase
from sentinel.schemas.evaluation import CaseEvaluation, MetricValue
from sentinel.schemas.generation import GenerationOutput
from sentinel.schemas.retrieval import RetrievalResult


def _retrieved_and_relevant_ids(case: DatasetCase, retrieval: RetrievalResult) -> tuple[list[str], set[str]]:
    if case.relevant_chunk_ids:
        return retrieval.chunk_ids(), set(case.relevant_chunk_ids)
    retrieved = [hit.chunk.document_id for hit in retrieval.hits]
    return retrieved, set(case.relevant_document_ids)


class CaseEvaluator:
    def __init__(self, top_k: int = 5, faithfulness_judge: MechanicalFaithfulnessJudge | None = None) -> None:
        self.top_k = top_k
        self.faithfulness_judge = faithfulness_judge or MechanicalFaithfulnessJudge()

    def evaluate(
        self, case: DatasetCase, retrieval: RetrievalResult, generation: GenerationOutput
    ) -> CaseEvaluation:
        metrics: dict[str, MetricValue] = {}

        retrieved_ids, relevant_ids = _retrieved_and_relevant_ids(case, retrieval)
        k = self.top_k
        metrics[f"recall_at_{k}"] = MetricValue(
            value=recall_at_k(retrieved_ids, relevant_ids, k), method="mechanical"
        )
        metrics[f"precision_at_{k}"] = MetricValue(
            value=precision_at_k(retrieved_ids, relevant_ids, k), method="mechanical"
        )
        metrics[f"hit_rate_at_{k}"] = MetricValue(
            value=hit_rate_at_k(retrieved_ids, relevant_ids, k), method="mechanical"
        )
        metrics["mrr"] = MetricValue(value=mrr(retrieved_ids, relevant_ids), method="mechanical")
        metrics[f"ndcg_at_{k}"] = MetricValue(
            value=ndcg_at_k(retrieved_ids, relevant_ids, k), method="mechanical"
        )

        refusal_outcome = RefusalOutcome(
            case_id=case.id, should_answer=case.should_answer, refused=generation.refused
        )
        metrics["refusal_label"] = MetricValue(value=None, method="mechanical", detail=refusal_outcome.label)

        chunks_by_id = {hit.chunk.id: hit.chunk.text for hit in retrieval.hits}
        if not generation.refused and generation.answer_text:
            claims = extract_claims(generation.answer_text)
            global_citation_ids = [c.chunk_id for c in generation.citations if c.claim_index is None]
            checks = check_citations(claims, global_citation_ids, chunks_by_id)
            metrics["citation_precision"] = MetricValue(value=citation_precision(checks), method="mechanical")
            metrics["citation_recall"] = MetricValue(value=citation_recall(checks), method="mechanical")

            verdicts = [
                self.faithfulness_judge.judge(c.claim, list(chunks_by_id.values())) for c in checks
            ]
            faithful = sum(1 for v in verdicts if v.supported) / len(verdicts) if verdicts else None
            metrics["faithfulness"] = MetricValue(
                value=faithful, method="mechanical", detail=self.faithfulness_judge.name
            )
        else:
            metrics["citation_precision"] = MetricValue(value=None, method="unavailable", detail="refused")
            metrics["citation_recall"] = MetricValue(value=None, method="unavailable", detail="refused")
            metrics["faithfulness"] = MetricValue(value=None, method="unavailable", detail="refused")

        references = case.acceptable_answers + ([case.reference_answer] if case.reference_answer else [])
        relevance = lexical_answer_relevance(generation.answer_text, references) if not generation.refused else None
        metrics["answer_relevance"] = MetricValue(
            value=relevance,
            method="mechanical" if relevance is not None else "unavailable",
        )

        metrics["latency_ms"] = MetricValue(value=retrieval.latency_ms + generation.latency_ms, method="mechanical")
        if generation.prompt_tokens is not None and generation.completion_tokens is not None:
            metrics["total_tokens"] = MetricValue(
                value=float(generation.prompt_tokens + generation.completion_tokens), method="mechanical"
            )
        if generation.estimated_cost_usd is not None:
            metrics["estimated_cost_usd"] = MetricValue(value=generation.estimated_cost_usd, method="mechanical")

        return CaseEvaluation(
            case_id=case.id,
            question=case.question,
            retrieval=retrieval,
            generation=generation,
            metrics=metrics,
            failures=[],
            passed=True,
        )
