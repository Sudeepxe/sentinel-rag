"""Embedding provider abstraction.

Sentinel ships a fully offline, deterministic embedding provider
(`HashingEmbeddingProvider`) so the core evaluation loop and CI never need
network access or API keys. It is a signed feature-hashing vectorizer over
word and character n-grams (a classical, real technique — not a neural
embedding model). It is honestly weaker at semantic (paraphrase/synonym)
matching than a trained sentence encoder; this is documented in
docs/architecture/overview.md and surfaced via `is_deterministic_local`.

`SentenceTransformerEmbeddingProvider` plugs in a real neural embedding
model when the optional `sentence-transformers` dependency is installed.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import numpy as np

from sentinel.retrieval.tokenize import tokenize


class EmbeddingProvider(ABC):
    name: str
    is_deterministic_local: bool = False
    dimensions: int

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (N, D) float32 array of L2-normalized embeddings."""


def _stable_hash(token: str) -> int:
    return int(hashlib.blake2b(token.encode("utf-8"), digest_size=8).hexdigest(), 16)


def _char_ngrams(word: str, n_range: tuple[int, int] = (3, 5)) -> list[str]:
    padded = f"#{word}#"
    grams: list[str] = []
    for n in range(n_range[0], n_range[1] + 1):
        if len(padded) < n:
            continue
        grams.extend(padded[i : i + n] for i in range(len(padded) - n + 1))
    return grams


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic, offline, signed hashing-trick vectorizer.

    Features = word unigrams/bigrams + character 3-5 grams, hashed into a
    fixed-width vector with a sign flip derived from the hash (reduces
    collision bias, standard hashing-vectorizer technique).
    """

    name = "hashing-local-v1"
    is_deterministic_local = True

    def __init__(self, dimensions: int = 512) -> None:
        self.dimensions = dimensions

    def _vectorize_one(self, text: str) -> np.ndarray:
        tokens = tokenize(text, remove_stopwords=True)
        # Fractional weights (char n-grams count at half weight), so this
        # is a plain float-valued dict rather than collections.Counter
        # (whose typeshed stub fixes counts to int).
        features: dict[str, float] = {}
        for tok in tokens:
            features[tok] = features.get(tok, 0.0) + 1
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]}_{tokens[i + 1]}"
            features[bigram] = features.get(bigram, 0.0) + 1
        for tok in tokens:
            for gram in _char_ngrams(tok):
                key = f"cg:{gram}"
                features[key] = features.get(key, 0.0) + 0.5

        vec = np.zeros(self.dimensions, dtype=np.float32)
        for feat, weight in features.items():
            h = _stable_hash(feat)
            idx = h % self.dimensions
            sign = 1.0 if (h // self.dimensions) % 2 == 0 else -1.0
            vec[idx] += sign * weight

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vectorize_one(t) for t in texts]) if texts else np.zeros(
            (0, self.dimensions), dtype=np.float32
        )


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Real neural embedding model. Requires `pip install sentinel-rag[embeddings]`.

    Not used by default (not deterministic across model versions/hardware
    and requires downloading model weights), but the architecture supports
    swapping it in via configs/models/*.yaml.
    """

    name = "sentence-transformers"
    is_deterministic_local = False

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. Install with "
                "`pip install sentinel-rag[embeddings]` to use this provider."
            ) from exc
        self._model = SentenceTransformer(model_name)
        self.dimensions = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimensions), dtype=np.float32)
        return np.asarray(
            self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        )
