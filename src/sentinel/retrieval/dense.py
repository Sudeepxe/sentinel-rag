from __future__ import annotations

import numpy as np

from sentinel.retrieval.embeddings import EmbeddingProvider
from sentinel.schemas.documents import Chunk


class DenseIndex:
    def __init__(self, chunks: list[Chunk], embedder: EmbeddingProvider) -> None:
        self.chunks = chunks
        self.embedder = embedder
        self._matrix = embedder.embed([c.text for c in chunks]) if chunks else np.zeros((0, 1))

    def score(self, query: str) -> list[float]:
        if not self.chunks:
            return []
        q_vec = self.embedder.embed([query])[0]
        sims = self._matrix @ q_vec
        return sims.tolist()

    def vector_for(self, index: int) -> np.ndarray:
        return self._matrix[index]
