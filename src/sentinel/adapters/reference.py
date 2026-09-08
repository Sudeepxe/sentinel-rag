"""ReferenceRAGAdapter: Sentinel's own real RAG pipeline.

Ingestion -> chunking -> BM25 + hashing-embedding dense index -> hybrid
RRF fusion -> optional reranking/MMR/query-rewrite/freshness -> extractive
or real-LLM generation. Fully configured by RetrievalConfig/GenerationConfig
so it doubles as the subject of Sentinel's own experiments (see
experiments/ablations).
"""

from __future__ import annotations

from sentinel.adapters.base import RAGSystem
from sentinel.generation.base import GenerationProvider
from sentinel.generation.factory import get_generation_provider
from sentinel.observability.tracing import span
from sentinel.retrieval.chunking import chunk_documents
from sentinel.retrieval.embeddings import EmbeddingProvider, HashingEmbeddingProvider
from sentinel.retrieval.retriever import HybridRetriever
from sentinel.schemas.documents import Document
from sentinel.schemas.experiments import GenerationConfig, RetrievalConfig
from sentinel.schemas.generation import GenerationOutput
from sentinel.schemas.retrieval import RetrievalResult


class ReferenceRAGAdapter(RAGSystem):
    name = "reference"

    def __init__(
        self,
        retrieval_config: RetrievalConfig | None = None,
        generation_config: GenerationConfig | None = None,
        embedder: EmbeddingProvider | None = None,
        generation_provider: GenerationProvider | None = None,
    ) -> None:
        self.retrieval_config = retrieval_config or RetrievalConfig()
        self.generation_config = generation_config or GenerationConfig()
        self.embedder = embedder or HashingEmbeddingProvider()
        self._generation_provider = generation_provider or get_generation_provider(
            self.generation_config.provider
        )
        self._retriever: HybridRetriever | None = None

    def ingest(self, documents: list[Document]) -> None:
        chunks = chunk_documents(
            documents,
            chunk_size=self.retrieval_config.chunk_size,
            chunk_overlap=self.retrieval_config.chunk_overlap,
        )
        self._retriever = HybridRetriever(chunks, config=self.retrieval_config, embedder=self.embedder)

    def retrieve(self, query: str) -> RetrievalResult:
        if self._retriever is None:
            raise RuntimeError("ingest() must be called before retrieve()")
        with span("retrieval", strategy=self.retrieval_config.strategy, top_k=self.retrieval_config.top_k):
            return self._retriever.retrieve(query)

    def generate(self, query: str, retrieval: RetrievalResult) -> GenerationOutput:
        with span(
            "generation", provider=self.generation_config.provider, evidence_chunks=len(retrieval.hits)
        ):
            return self._generation_provider.generate(query, retrieval.hits, self.generation_config)

    def full_ranking(self, query: str) -> list[str] | None:
        if self._retriever is None:
            raise RuntimeError("ingest() must be called before full_ranking()")
        return self._retriever.full_ranking(query)
