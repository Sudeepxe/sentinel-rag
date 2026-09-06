"""RAG adapter interface.

Sentinel does not hard-code itself to its own RAG implementation. Anything
implementing this Protocol — Sentinel's own ReferenceRAGAdapter, or a
thin wrapper around an external RAG service — can be evaluated,
diagnosed, attacked, and repaired by the rest of the toolkit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sentinel.schemas.documents import Document
from sentinel.schemas.generation import GenerationOutput
from sentinel.schemas.retrieval import RetrievalResult


class AnswerBundle:
    __slots__ = ("retrieval", "generation")

    def __init__(self, retrieval: RetrievalResult, generation: GenerationOutput) -> None:
        self.retrieval = retrieval
        self.generation = generation


class RAGSystem(ABC):
    """Interface every adapter (reference or external) must implement."""

    name: str

    @abstractmethod
    def ingest(self, documents: list[Document]) -> None:
        """Load/index a corpus. Called once per evaluated case or dataset."""

    @abstractmethod
    def retrieve(self, query: str) -> RetrievalResult:
        """Return ranked evidence for a query, with scores and metadata."""

    @abstractmethod
    def generate(self, query: str, retrieval: RetrievalResult) -> GenerationOutput:
        """Produce an answer + citations from the given evidence."""

    def answer(self, query: str) -> AnswerBundle:
        """Convenience: retrieve then generate in one call."""
        retrieval = self.retrieve(query)
        generation = self.generate(query, retrieval)
        return AnswerBundle(retrieval=retrieval, generation=generation)

    def full_ranking(self, query: str) -> list[str] | None:
        """Optional: full corpus ranking (chunk or document ids, best first)
        beyond the top-k returned by retrieve(). Used by the diagnosis
        engine to find the true rank of a missed relevant item (e.g. "rank
        17, outside top-5") instead of only knowing "not in top-k".
        External adapters that can't expose this return None, and
        diagnosis degrades to a coarser "not found in top-k" signal.
        """
        return None
