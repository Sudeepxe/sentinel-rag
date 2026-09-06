"""Reranker abstraction.

`LexicalOverlapReranker` is a deterministic local baseline (token-overlap
Jaccard between query and chunk, tie-broken by original score). It is
intentionally simple; the interface is where a real cross-encoder
(e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) would plug in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sentinel.retrieval.tokenize import tokenize
from sentinel.schemas.documents import Chunk


class Reranker(ABC):
    name: str

    @abstractmethod
    def rerank(self, query: str, chunks: list[Chunk]) -> list[float]:
        """Return a rerank score per chunk, same order as input."""


class LexicalOverlapReranker(Reranker):
    name = "lexical-overlap-local"

    def rerank(self, query: str, chunks: list[Chunk]) -> list[float]:
        q_tokens = set(tokenize(query))
        scores = []
        for chunk in chunks:
            c_tokens = set(tokenize(chunk.text))
            if not q_tokens or not c_tokens:
                scores.append(0.0)
                continue
            overlap = len(q_tokens & c_tokens) / len(q_tokens | c_tokens)
            scores.append(overlap)
        return scores
