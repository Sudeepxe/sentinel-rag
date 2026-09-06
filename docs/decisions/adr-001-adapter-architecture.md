# ADR-001: Why an Adapter Architecture for RAG Systems Under Test

## Context

Sentinel-RAG's entire value proposition is evaluating, diagnosing, and repairing RAG systems — not
being one. If the evaluation/diagnosis/repair machinery were written against Sentinel's own
retrieval and generation code directly, it could never be pointed at a third-party RAG system, and
the project would collapse into "a RAG demo with a benchmark script," which the spec explicitly
rules out.

## Decision

Define `sentinel.adapters.base.RAGSystem` as a minimal, provider-agnostic interface
(`ingest`, `retrieve`, `generate`, optional `full_ranking`) that every subject-under-test must
implement. All of `sentinel.evaluation`, `sentinel.diagnosis`, `sentinel.repair`, and
`sentinel.attacks` depend only on this interface's output schemas (`RetrievalResult`,
`GenerationOutput`), never on `ReferenceRAGAdapter`'s internals. Ship `ReferenceRAGAdapter` (a real
BM25+dense+RRF pipeline) as one implementation and `DeterministicTestAdapter` (canned outputs) as
another, so the interface is exercised by two structurally different adapters from day one.

## Alternatives Considered

- **Evaluate only Sentinel's own reference pipeline.** Rejected: this is exactly the "RAG demo"
  shape the project is explicitly not supposed to be, and would make the tool useless for anyone
  with an existing RAG system.
- **A plugin/hook system with lifecycle callbacks** (pre-retrieve, post-generate, etc.) instead of
  a simple three-method interface. Rejected as premature: no current requirement needs
  finer-grained hooks, and a wider interface is a wider thing external adapters must implement
  correctly.

## Consequences

- Any RAG system, in any language/framework, can be evaluated by writing one Python class (or a
  thin HTTP-calling adapter) implementing three methods.
- `full_ranking` is optional specifically because most external systems won't expose a full
  pre-truncation ranking; diagnosis degrades gracefully (coarser "not in top-k" signal instead of
  an exact miss-rank) rather than requiring it.
- The interface is intentionally synchronous; a system that's only reachable via a slow HTTP API
  will make evaluation slow. Async support is not implemented in v1 (documented, not silently
  assumed away).
