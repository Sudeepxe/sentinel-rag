"""Failure-type -> candidate repair mapping (spec section 19).

Each entry is a function (base_config) -> RepairProposal | None (some
repairs don't apply, e.g. "enable hybrid retrieval" is a no-op if already
hybrid). Repairs only ever *propose* a config; they never claim to have
fixed anything — that requires sentinel.repair.acceptance running a real
controlled experiment.
"""

from __future__ import annotations

from collections.abc import Callable

from sentinel.schemas.experiments import ExperimentConfig
from sentinel.schemas.failures import FailureType
from sentinel.schemas.repair import RepairProposal

RepairFactory = Callable[[ExperimentConfig, str], RepairProposal | None]


def _bump_top_k(base: ExperimentConfig, repair_id: str) -> RepairProposal | None:
    new_k = base.retrieval.top_k * 2
    cfg = base.model_copy(deep=True)
    cfg.retrieval.top_k = new_k
    cfg.name = f"{base.name}+top_k={new_k}"
    return RepairProposal(
        repair_id=repair_id,
        failure_type=FailureType.MISSING_RELEVANT_CHUNK,
        proposed_change=f"increase retrieval top_k from {base.retrieval.top_k} to {new_k}",
        rationale="relevant evidence is being found but ranked outside the retrieval window",
        expected_effect="higher recall@k at the cost of more context tokens and latency",
        risk="low: more candidates considered, may slightly increase generation latency/cost",
        experiment_config=cfg,
    )


def _enable_hybrid(base: ExperimentConfig, repair_id: str) -> RepairProposal | None:
    if base.retrieval.strategy == "hybrid_rrf":
        return None
    cfg = base.model_copy(deep=True)
    cfg.retrieval.strategy = "hybrid_rrf"
    cfg.name = f"{base.name}+hybrid_rrf"
    return RepairProposal(
        repair_id=repair_id,
        failure_type=FailureType.SEMANTIC_MISMATCH,
        proposed_change=f"switch retrieval strategy from {base.retrieval.strategy!r} to 'hybrid_rrf'",
        rationale="single-strategy retrieval misses cases the other strategy would catch "
        "(lexical mismatch for dense-only, paraphrase mismatch for BM25-only)",
        expected_effect="recall@k improves by combining lexical and embedding signal via RRF",
        risk="low: hybrid fusion strictly widens the candidate pool before top_k truncation",
        experiment_config=cfg,
    )


def _enable_reranker(base: ExperimentConfig, repair_id: str) -> RepairProposal | None:
    if base.retrieval.use_reranker:
        return None
    cfg = base.model_copy(deep=True)
    cfg.retrieval.use_reranker = True
    cfg.retrieval.rerank_top_n = max(cfg.retrieval.top_k * 4, 20)
    cfg.name = f"{base.name}+reranker"
    return RepairProposal(
        repair_id=repair_id,
        failure_type=FailureType.WRONG_RANKING,
        proposed_change="enable reranking over a wider candidate pool before truncating to top_k",
        rationale="the relevant chunk is retrieved but not ranked highly by first-stage scoring",
        expected_effect="improves ranking quality (MRR/nDCG) without changing what's retrievable",
        risk="medium: adds reranking latency proportional to rerank_top_n",
        experiment_config=cfg,
    )


def _enable_query_rewrite(base: ExperimentConfig, repair_id: str) -> RepairProposal | None:
    if base.retrieval.query_rewrite != "none":
        return None
    cfg = base.model_copy(deep=True)
    cfg.retrieval.query_rewrite = "expansion"
    cfg.name = f"{base.name}+query_expansion"
    return RepairProposal(
        repair_id=repair_id,
        failure_type=FailureType.QUERY_FORMULATION_FAILURE,
        proposed_change="enable query-expansion rewriting before retrieval",
        rationale="the literal query wording differs from the source document's terminology",
        expected_effect="recall@k improves for terminology-mismatch cases; may add noise for others",
        risk="medium: expansion can dilute precision for already-easy queries",
        experiment_config=cfg,
    )


def _reduce_chunk_size(base: ExperimentConfig, repair_id: str) -> RepairProposal | None:
    if base.retrieval.chunk_size <= 150:
        return None
    new_size = max(150, base.retrieval.chunk_size // 2)
    cfg = base.model_copy(deep=True)
    cfg.retrieval.chunk_size = new_size
    cfg.retrieval.chunk_overlap = min(cfg.retrieval.chunk_overlap, new_size // 4)
    cfg.name = f"{base.name}+chunk_size={new_size}"
    return RepairProposal(
        repair_id=repair_id,
        failure_type=FailureType.EVIDENCE_OVERLOAD,
        proposed_change=f"reduce chunk_size from {base.retrieval.chunk_size} to {new_size}",
        rationale="large chunks mix relevant and irrelevant content, diluting lexical/embedding scores",
        expected_effect="sharper retrieval scoring and less irrelevant context reaching generation",
        risk="medium: smaller chunks may split relevant context across chunk boundaries",
        experiment_config=cfg,
    )


def _lower_refusal_threshold(base: ExperimentConfig, repair_id: str) -> RepairProposal | None:
    new_threshold = max(0.0, base.generation.refuse_below_evidence_score - 0.05)
    if new_threshold == base.generation.refuse_below_evidence_score:
        return None
    cfg = base.model_copy(deep=True)
    cfg.generation.refuse_below_evidence_score = new_threshold
    cfg.name = f"{base.name}+refusal_threshold={new_threshold:.2f}"
    return RepairProposal(
        repair_id=repair_id,
        failure_type=FailureType.FALSE_REFUSAL,
        proposed_change=f"lower refuse_below_evidence_score from "
        f"{base.generation.refuse_below_evidence_score:.2f} to {new_threshold:.2f}",
        rationale="system is refusing on cases that do have usable (if weak) evidence",
        expected_effect="false_refusal_rate decreases; risk of unsafe_answer_rate increasing",
        risk="medium: directly trades off against unsafe_answer_rate, must check acceptance criteria",
        experiment_config=cfg,
    )


def _raise_refusal_threshold(base: ExperimentConfig, repair_id: str) -> RepairProposal | None:
    new_threshold = min(1.0, base.generation.refuse_below_evidence_score + 0.05)
    if new_threshold == base.generation.refuse_below_evidence_score:
        return None
    cfg = base.model_copy(deep=True)
    cfg.generation.refuse_below_evidence_score = new_threshold
    cfg.name = f"{base.name}+refusal_threshold={new_threshold:.2f}"
    return RepairProposal(
        repair_id=repair_id,
        failure_type=FailureType.ANSWERED_UNANSWERABLE,
        proposed_change=f"raise refuse_below_evidence_score from "
        f"{base.generation.refuse_below_evidence_score:.2f} to {new_threshold:.2f}",
        rationale="system is answering unanswerable questions instead of refusing",
        expected_effect="unsafe_answer_rate decreases; risk of false_refusal_rate increasing",
        risk="medium: directly trades off against false_refusal_rate, must check acceptance criteria",
        experiment_config=cfg,
    )


def _enable_mmr(base: ExperimentConfig, repair_id: str) -> RepairProposal | None:
    if base.retrieval.use_mmr:
        return None
    cfg = base.model_copy(deep=True)
    cfg.retrieval.use_mmr = True
    cfg.name = f"{base.name}+mmr"
    return RepairProposal(
        repair_id=repair_id,
        failure_type=FailureType.DUPLICATED_EVIDENCE,
        proposed_change="enable MMR diversification when selecting the top_k context chunks",
        rationale="retrieved context contains near-duplicate chunks crowding out distinct evidence",
        expected_effect="more diverse evidence set for the same top_k budget",
        risk="low: may slightly reduce precision if duplicates were actually the best matches",
        experiment_config=cfg,
    )


_CATALOG: dict[FailureType, list[RepairFactory]] = {
    FailureType.MISSING_RELEVANT_CHUNK: [_bump_top_k, _enable_hybrid, _enable_query_rewrite],
    FailureType.WRONG_RANKING: [_enable_reranker, _enable_hybrid],
    FailureType.SEMANTIC_MISMATCH: [_enable_hybrid, _enable_query_rewrite],
    FailureType.QUERY_FORMULATION_FAILURE: [_enable_query_rewrite],
    FailureType.EVIDENCE_OVERLOAD: [_reduce_chunk_size],
    FailureType.DUPLICATED_EVIDENCE: [_enable_mmr],
    FailureType.FALSE_REFUSAL: [_lower_refusal_threshold],
    FailureType.ANSWERED_UNANSWERABLE: [_raise_refusal_threshold],
    FailureType.REFUSAL_WITHOUT_EVIDENCE: [_raise_refusal_threshold],
}


def repairs_for(failure_type: FailureType) -> list[RepairFactory]:
    return _CATALOG.get(failure_type, [])
