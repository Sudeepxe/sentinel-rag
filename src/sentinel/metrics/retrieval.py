"""Standard IR metrics, computed mechanically (no LLM involved).

All functions take:
- retrieved_ids: ranked list of chunk/doc ids returned by retrieval, best first
- relevant_ids: the ground-truth relevant set (unordered)
"""

from __future__ import annotations

import math


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for rid in top_k if rid in relevant_ids)
    return hits / len(top_k)


def hit_rate_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    return 1.0 if set(retrieved_ids[:k]) & relevant_ids else 0.0


def mrr(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    top_k = retrieved_ids[:k]
    # A relevant id can only contribute gain once: with document-granularity
    # matching, multiple chunks from the same relevant document can appear
    # in top_k, and re-counting each occurrence would push nDCG above 1.0.
    seen: set[str] = set()
    dcg = 0.0
    for i, rid in enumerate(top_k):
        if rid in relevant_ids and rid not in seen:
            dcg += 1.0 / math.log2(i + 2)
            seen.add(rid)
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0
