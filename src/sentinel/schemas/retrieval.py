from __future__ import annotations

from pydantic import BaseModel, Field

from sentinel.schemas.documents import Chunk


class RetrievalHit(BaseModel):
    chunk: Chunk
    score: float
    rank: int
    bm25_score: float | None = None
    dense_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None


class RetrievalResult(BaseModel):
    query: str
    strategy: str
    hits: list[RetrievalHit]
    latency_ms: float
    rewritten_queries: list[str] = Field(default_factory=list)

    def chunk_ids(self) -> list[str]:
        return [h.chunk.id for h in self.hits]
