"""DeterministicTestAdapter: a canned, fixture-driven adapter used to test
Sentinel's own evaluation/diagnosis/repair machinery in isolation from
retrieval or generation quality. Not a RAG system under test — a stub
target used by Sentinel's own unit/integration tests and by anyone
wiring Sentinel against a system where they want to inject known
retrieval/generation outputs to test the harness deterministically.
"""

from __future__ import annotations

from sentinel.adapters.base import RAGSystem
from sentinel.schemas.documents import Document
from sentinel.schemas.generation import GenerationOutput
from sentinel.schemas.retrieval import RetrievalHit, RetrievalResult


class DeterministicTestAdapter(RAGSystem):
    name = "deterministic_test"

    def __init__(
        self,
        canned_hits: dict[str, list[RetrievalHit]] | None = None,
        canned_answers: dict[str, GenerationOutput] | None = None,
    ) -> None:
        self._canned_hits = canned_hits or {}
        self._canned_answers = canned_answers or {}
        self._documents: list[Document] = []

    def ingest(self, documents: list[Document]) -> None:
        self._documents = documents

    def retrieve(self, query: str) -> RetrievalResult:
        hits = self._canned_hits.get(query, [])
        return RetrievalResult(query=query, strategy="canned", hits=hits, latency_ms=0.0)

    def generate(self, query: str, retrieval: RetrievalResult) -> GenerationOutput:
        if query in self._canned_answers:
            return self._canned_answers[query]
        return GenerationOutput(
            answer_text="",
            refused=True,
            citations=[],
            provider="deterministic_test",
            model="canned",
            latency_ms=0.0,
            is_deterministic_local=True,
        )
