"""HybridRetriever: orchestrates BM25, dense, RRF fusion, MMR, reranking,
query rewriting, and freshness policies behind one configurable interface.

Strategy names (RetrievalConfig.strategy):
- "bm25": lexical only
- "dense": embedding cosine similarity only
- "hybrid_rrf": BM25 + dense fused via Reciprocal Rank Fusion (default)
"""

from __future__ import annotations

import time

from sentinel.retrieval.bm25 import BM25Index
from sentinel.retrieval.dense import DenseIndex
from sentinel.retrieval.embeddings import EmbeddingProvider, HashingEmbeddingProvider
from sentinel.retrieval.freshness import apply_freshness_policy
from sentinel.retrieval.fusion import mmr_select, reciprocal_rank_fusion
from sentinel.retrieval.query_rewrite import apply_strategy
from sentinel.retrieval.reranker import LexicalOverlapReranker, Reranker
from sentinel.schemas.documents import Chunk
from sentinel.schemas.experiments import RetrievalConfig
from sentinel.schemas.retrieval import RetrievalHit, RetrievalResult

VALID_STRATEGIES = ("bm25", "dense", "hybrid_rrf")


def _apply_metadata_filter(chunks: list[Chunk], metadata_filter: dict[str, str]) -> list[Chunk]:
    """Exact-match filter over chunk.source plus chunk.metadata, applied
    before indexing so a filtered-out chunk can never be retrieved
    (rather than retrieved-then-discarded, which would corrupt top_k
    accounting). A filter matching zero chunks is a real, reportable
    METADATA_FILTERING_FAILURE, not silently ignored.
    """
    if not metadata_filter:
        return chunks
    filtered = []
    for chunk in chunks:
        fields = {"source": chunk.source, **chunk.metadata}
        if all(fields.get(key) == value for key, value in metadata_filter.items()):
            filtered.append(chunk)
    return filtered


class HybridRetriever:
    def __init__(
        self,
        chunks: list[Chunk],
        config: RetrievalConfig | None = None,
        embedder: EmbeddingProvider | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.config = config or RetrievalConfig()
        if self.config.strategy not in VALID_STRATEGIES:
            raise ValueError(f"unknown retrieval strategy: {self.config.strategy!r}")
        self.chunks = _apply_metadata_filter(chunks, self.config.metadata_filter)
        self.embedder = embedder or HashingEmbeddingProvider()
        self.reranker = reranker or LexicalOverlapReranker()
        self._by_id = {c.id: c for c in self.chunks}
        self.bm25 = BM25Index(self.chunks) if self.chunks else None
        self.dense = DenseIndex(self.chunks, self.embedder) if self.chunks else None

    def _score_single_query(self, query: str) -> dict[str, float]:
        if not self.chunks:
            return {}
        strategy = self.config.strategy
        if strategy == "bm25":
            scores = self.bm25.score(query)  # type: ignore[union-attr]
            return {c.id: s for c, s in zip(self.chunks, scores, strict=True)}
        if strategy == "dense":
            scores = self.dense.score(query)  # type: ignore[union-attr]
            return {c.id: s for c, s in zip(self.chunks, scores, strict=True)}

        # hybrid_rrf
        bm25_scores = self.bm25.score(query)  # type: ignore[union-attr]
        dense_scores = self.dense.score(query)  # type: ignore[union-attr]
        bm25_ranking = [
            c.id for c, _ in sorted(zip(self.chunks, bm25_scores, strict=True), key=lambda x: -x[1])
        ]
        dense_ranking = [
            c.id for c, _ in sorted(zip(self.chunks, dense_scores, strict=True), key=lambda x: -x[1])
        ]
        return reciprocal_rank_fusion([bm25_ranking, dense_ranking])

    def retrieve(self, query: str) -> RetrievalResult:
        start = time.perf_counter()
        rewritten = apply_strategy(self.config.query_rewrite, query)

        combined: dict[str, float] = {}
        for q in rewritten:
            partial = self._score_single_query(q)
            for cid, score in partial.items():
                combined[cid] = max(combined.get(cid, -float("inf")), score)

        candidate_ids = list(combined.keys())
        candidate_ids.sort(key=lambda cid: -combined[cid])

        pool_size = max(self.config.top_k, self.config.rerank_top_n if self.config.use_reranker else 0)
        pool_ids = candidate_ids[:pool_size] if pool_size else candidate_ids

        pool_chunks = [self._by_id[cid] for cid in pool_ids]
        rerank_scores: dict[str, float] = {}
        if self.config.use_reranker and pool_chunks:
            rr = self.reranker.rerank(query, pool_chunks)
            rerank_scores = {c.id: s for c, s in zip(pool_chunks, rr, strict=True)}
            pool_ids.sort(key=lambda cid: -rerank_scores[cid])

        freshness_scores = combined
        if self.config.freshness_policy != "no-preference" and pool_ids:
            base = [rerank_scores.get(cid, combined[cid]) for cid in pool_ids]
            adjusted = apply_freshness_policy(pool_chunks, base, self.config.freshness_policy)
            freshness_scores = dict(zip(pool_ids, adjusted, strict=True))
            pool_ids.sort(key=lambda cid: -freshness_scores[cid])

        if self.config.use_mmr and pool_ids:
            vectors = {cid: self.dense.vector_for(self._index_of(cid)) for cid in pool_ids}  # type: ignore[union-attr]
            relevance = {cid: freshness_scores.get(cid, combined[cid]) for cid in pool_ids}
            pool_ids = mmr_select(pool_ids, relevance, vectors, self.config.top_k, self.config.mmr_lambda)
        else:
            pool_ids = pool_ids[: self.config.top_k]

        hits = []
        for rank, cid in enumerate(pool_ids, start=1):
            chunk = self._by_id[cid]
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    score=freshness_scores.get(cid, combined.get(cid, 0.0)),
                    rank=rank,
                    bm25_score=None,
                    dense_score=None,
                    fusion_score=combined.get(cid),
                    rerank_score=rerank_scores.get(cid),
                )
            )

        latency_ms = (time.perf_counter() - start) * 1000
        return RetrievalResult(
            query=query,
            strategy=self.config.strategy,
            hits=hits,
            latency_ms=latency_ms,
            rewritten_queries=rewritten,
        )

    def full_ranking(self, query: str) -> list[str]:
        """Full candidate ranking (all scored chunks, best first), before
        top_k truncation, rerank, MMR, or freshness re-scoring. Used by
        diagnosis to find the true rank of a chunk missed from the top-k.
        """
        combined = self._score_single_query(query)
        if self.config.query_rewrite != "none":
            for q in apply_strategy(self.config.query_rewrite, query)[1:]:
                partial = self._score_single_query(q)
                for cid, score in partial.items():
                    combined[cid] = max(combined.get(cid, -float("inf")), score)
        return sorted(combined, key=lambda cid: -combined[cid])

    def _index_of(self, chunk_id: str) -> int:
        for i, c in enumerate(self.chunks):
            if c.id == chunk_id:
                return i
        raise KeyError(chunk_id)
