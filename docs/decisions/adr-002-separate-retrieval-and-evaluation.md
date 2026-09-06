# ADR-002: Why Retrieval and Evaluation Are Separate Packages

## Context

`sentinel.retrieval` implements real retrieval (BM25, embeddings, fusion, reranking).
`sentinel.evaluation` implements the logic that scores retrieval/generation output against ground
truth. These could live in one package — evaluation logic is "close to" retrieval conceptually —
but doing so would let evaluation code accidentally depend on `HybridRetriever` internals instead
of the `RetrievalResult` schema, which would break the moment an external adapter (ADR-001)
produces retrieval results some other way.

## Decision

`sentinel.evaluation` (and `sentinel.diagnosis`, `sentinel.repair`, `sentinel.attacks`) may only
import `sentinel.schemas` and `sentinel.metrics` — never `sentinel.retrieval` or
`sentinel.generation` internals. The one narrow exception is `sentinel.diagnosis.rules`, which
receives an already-computed `full_ranking: list[str]` (plain strings) rather than reaching into a
`HybridRetriever` object.

## Alternatives Considered

- **One `sentinel.rag` package containing retrieval + evaluation together**, since they're
  conceptually adjacent. Rejected: this is exactly the coupling that would make evaluating an
  external system impossible without either duplicating evaluation logic or forcing the external
  system's retrieval through Sentinel's own retriever classes.
- **A shared "context" object threaded through every layer** carrying both the RetrievalResult and
  retriever-internal state. Rejected as unnecessary indirection; the schema objects
  (`RetrievalResult`, `GenerationOutput`) already carry everything evaluation needs.

## Consequences

- Evaluation, diagnosis, and repair work identically whether the retrieval came from
  `ReferenceRAGAdapter`, a hand-written `DeterministicTestAdapter` fixture, or a real external
  system wrapped in a custom adapter.
- Any evaluation feature that needs retrieval-internal information (e.g., "what would the score
  have been under BM25 alone") must be exposed through the schema or the `RAGSystem` interface
  explicitly (as `full_ranking` was), not accessed by reaching into retriever objects.
