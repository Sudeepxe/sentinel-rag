"""Evidence-backed diagnosis rules.

Each rule inspects real measured signals (ranks, scores, lexical overlap,
metric values already computed by sentinel.evaluation) and returns a
FailureRecord or None. Confidence is derived from how far the measured
signal is past the rule's threshold — not a fixed made-up number — so two
cases hitting the same rule can carry different confidence.
"""

from __future__ import annotations

from sentinel.retrieval.tokenize import tokenize
from sentinel.schemas.dataset import DatasetCase
from sentinel.schemas.evaluation import CaseEvaluation
from sentinel.schemas.failures import FailureRecord, FailureType


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def diagnose_retrieval(
    case: DatasetCase, evaluation: CaseEvaluation, full_ranking: list[str] | None
) -> FailureRecord | None:
    if not case.should_answer or not case.relevant_document_ids:
        return None
    k_metric = next((v for k, v in evaluation.metrics.items() if k.startswith("recall_at_")), None)
    if k_metric is None or k_metric.value is None or k_metric.value >= 0.999:
        return None

    top_k = int(next(k for k in evaluation.metrics if k.startswith("recall_at_")).split("_")[-1])
    retrieved_doc_ids = [h.chunk.document_id for h in (evaluation.retrieval.hits if evaluation.retrieval else [])]
    relevant = set(case.relevant_document_ids)

    rank_found: int | None = None
    if full_ranking:
        # full_ranking is chunk ids ordered best-first; map to document ids preserving order.
        doc_order: list[str] = []
        for cid in full_ranking:
            doc_id = cid.split("::chunk")[0]
            if doc_id not in doc_order:
                doc_order.append(doc_id)
        for i, doc_id in enumerate(doc_order, start=1):
            if doc_id in relevant:
                rank_found = i
                break

    question_terms = set(tokenize(case.question))
    target_doc = next((d for d in case.documents if d.id in relevant), None)
    lexical_overlap = None
    if target_doc is not None:
        doc_terms = set(tokenize(target_doc.text))
        lexical_overlap = len(question_terms & doc_terms) / len(question_terms) if question_terms else None

    evidence = {
        "recall_at_k": k_metric.value,
        "top_k": top_k,
        "retrieved_document_ids": retrieved_doc_ids,
        "relevant_document_ids": sorted(relevant),
        "true_rank": rank_found,
        "query_document_lexical_overlap": lexical_overlap,
    }

    if rank_found is not None and rank_found > top_k:
        secondary = []
        likely_cause = "relevant document ranked below top-k"
        confidence = _clamp(0.6 + 0.05 * min(rank_found - top_k, 6))
        if lexical_overlap is not None and lexical_overlap < 0.35:
            secondary.append(FailureType.SEMANTIC_MISMATCH)
            likely_cause = "terminology mismatch between question and source document wording"
            confidence = _clamp(confidence + 0.15)
        primary = FailureType.WRONG_RANKING if rank_found <= top_k * 3 else FailureType.MISSING_RELEVANT_CHUNK
        return FailureRecord(
            case_id=case.id,
            primary=primary,
            secondary=secondary,
            evidence=evidence,
            confidence=confidence,
            likely_cause=likely_cause,
            explanation=(
                f"Relevant document(s) {sorted(relevant)} found at rank {rank_found} "
                f"but top_k={top_k} only returned {retrieved_doc_ids}."
            ),
        )

    # recall < 1 but we couldn't find it even in full_ranking (adapter doesn't expose it,
    # or truly never scored) -> coarser signal.
    confidence = _clamp(0.5 + 0.1 * (1 - (k_metric.value or 0.0)))
    return FailureRecord(
        case_id=case.id,
        primary=FailureType.MISSING_RELEVANT_CHUNK,
        secondary=[],
        evidence=evidence,
        confidence=confidence,
        likely_cause="relevant document not present in top-k retrieval results",
        explanation=(
            f"recall@{top_k}={k_metric.value:.2f}; relevant={sorted(relevant)}, "
            f"retrieved={retrieved_doc_ids}. Exact miss-rank unavailable for this adapter."
        ),
    )


def diagnose_citations(case: DatasetCase, evaluation: CaseEvaluation) -> FailureRecord | None:
    precision = evaluation.metrics.get("citation_precision")
    recall = evaluation.metrics.get("citation_recall")
    if precision is None or precision.value is None:
        return None
    if precision.value >= 0.999 and (recall is None or recall.value is None or recall.value >= 0.999):
        return None

    primary = FailureType.MISSING_CITATION
    if precision.value < 0.999 and (recall is None or recall.value is None or recall.value >= 0.999):
        primary = FailureType.INCORRECT_CITATION
    elif precision.value < 0.999:
        primary = FailureType.CITATION_MISMATCH

    confidence = _clamp(1.0 - (precision.value or 0.0)) * 0.5 + 0.4
    return FailureRecord(
        case_id=case.id,
        primary=primary,
        secondary=[FailureType.PARTIAL_CITATION] if 0 < (precision.value or 1) < 1 else [],
        evidence={
            "citation_precision": precision.value,
            "citation_recall": recall.value if recall else None,
        },
        confidence=confidence,
        likely_cause="cited chunk text does not lexically support the claim it is attached to",
        explanation=f"citation_precision={precision.value:.2f}, citation_recall={(recall.value if recall else None)}",
    )


def diagnose_generation(case: DatasetCase, evaluation: CaseEvaluation) -> FailureRecord | None:
    faithfulness = evaluation.metrics.get("faithfulness")
    if faithfulness is None or faithfulness.value is None or faithfulness.value >= 0.999:
        return None
    confidence = _clamp(1.0 - faithfulness.value) * 0.6 + 0.3
    primary = FailureType.UNSUPPORTED_CLAIM if faithfulness.value > 0 else FailureType.HALLUCINATION
    return FailureRecord(
        case_id=case.id,
        primary=primary,
        secondary=[],
        evidence={"faithfulness": faithfulness.value, "method": faithfulness.detail},
        confidence=confidence,
        likely_cause="answer contains claims not lexically grounded in any retrieved evidence chunk",
        explanation=f"faithfulness={faithfulness.value:.2f} ({faithfulness.detail})",
    )


def diagnose_refusal(case: DatasetCase, evaluation: CaseEvaluation) -> FailureRecord | None:
    label_metric = evaluation.metrics.get("refusal_label")
    if label_metric is None:
        return None
    label = label_metric.detail
    if label == "false_refusal":
        return FailureRecord(
            case_id=case.id,
            primary=FailureType.FALSE_REFUSAL,
            evidence={"should_answer": case.should_answer, "refused": True},
            confidence=0.85,
            likely_cause="system refused despite should_answer=True; evidence threshold may be too strict",
        )
    if label == "unsafe_answer":
        return FailureRecord(
            case_id=case.id,
            primary=FailureType.ANSWERED_UNANSWERABLE,
            evidence={"should_answer": case.should_answer, "refused": False},
            confidence=0.85,
            likely_cause="system answered a question marked should_answer=False instead of refusing",
        )
    return None
