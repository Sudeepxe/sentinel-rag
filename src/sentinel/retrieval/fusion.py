"""Reciprocal Rank Fusion and Maximal Marginal Relevance."""

from __future__ import annotations

import numpy as np


def reciprocal_rank_fusion(
    rankings: list[list[str]], k: int = 60, weights: list[float] | None = None
) -> dict[str, float]:
    """Combine multiple ranked ID lists into fused scores.

    Standard RRF: score(d) = sum over rankers of weight / (k + rank(d)).
    """
    if weights is None:
        weights = [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError("weights must match number of rankings")

    fused: dict[str, float] = {}
    for ranking, weight in zip(rankings, weights, strict=True):
        for rank, doc_id in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + weight / (k + rank)
    return fused


def mmr_select(
    candidate_ids: list[str],
    relevance: dict[str, float],
    vectors: dict[str, np.ndarray],
    top_k: int,
    lambda_mult: float = 0.5,
) -> list[str]:
    """Maximal Marginal Relevance re-ordering to reduce redundancy."""
    selected: list[str] = []
    remaining = list(candidate_ids)

    def _sim(a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
        return float(np.dot(a, b) / denom)

    while remaining and len(selected) < top_k:
        best_id, best_score = None, -float("inf")
        for cid in remaining:
            rel = relevance.get(cid, 0.0)
            redundancy = max(_sim(vectors[cid], vectors[s]) for s in selected) if selected else 0.0
            score = lambda_mult * rel - (1 - lambda_mult) * redundancy
            if score > best_score:
                best_score, best_id = score, cid
        selected.append(best_id)  # type: ignore[arg-type]
        remaining.remove(best_id)  # type: ignore[arg-type]
    return selected
