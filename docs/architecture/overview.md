# Architecture Overview

## System shape

```
Dataset (EvaluationDataset)
  -> RAGSystem adapter (ReferenceRAGAdapter | external adapter)
       -> retrieve(query) -> RetrievalResult
       -> generate(query, RetrievalResult) -> GenerationOutput
  -> CaseEvaluator -> CaseEvaluation (metrics: retrieval/citation/faithfulness/refusal)
  -> DiagnosisEngine -> FailureRecord[] (evidence-backed, taxonomy-anchored)
  -> RepairEngine -> RepairProposal[] (config deltas, not applied automatically)
  -> ExperimentRunner (baseline vs. candidate) -> ExperimentResult
  -> RepairEngine.acceptance -> RepairDecision (accept/reject, real thresholds)
  -> ReportBundle -> Markdown/JSON/HTML
```

Everything left of `ExperimentRunner` is also directly exercised by `sentinel attack`
(`AttackRunner` swaps `CaseEvaluator` for `classify_attack_result`) and by ad hoc scripts like
`scripts/run_all_experiments.py`.

## Module boundaries

| Package | Responsibility | Must not depend on |
|---|---|---|
| `sentinel.schemas` | Pydantic data contracts shared by every other package | anything else in `sentinel` |
| `sentinel.retrieval` | Chunking, BM25, embeddings, dense index, fusion, reranking, freshness, conflict detection | `sentinel.generation`, `sentinel.evaluation` |
| `sentinel.generation` | Generation provider interface + deterministic/OpenAI/Anthropic implementations | `sentinel.retrieval` internals (only `schemas.retrieval.RetrievalHit`) |
| `sentinel.adapters` | `RAGSystem` interface + `ReferenceRAGAdapter` (wires retrieval+generation) | — |
| `sentinel.metrics` | Pure functions: IR metrics, citation lexical-support scoring, refusal classification | no I/O, no config |
| `sentinel.evaluation` | Orchestrates metrics into a `CaseEvaluation`; faithfulness judge abstraction | — |
| `sentinel.diagnosis` | Evidence-backed failure-taxonomy rules + engine | — |
| `sentinel.repair` | Failure -> config-delta catalog, acceptance-criteria gate | — |
| `sentinel.experiments` | Reproducible run harness, bootstrap stats, ablation runner | — |
| `sentinel.attacks` | Attack generation, classification, poisoning-curve experiment | `sentinel.adapters` (runs cases through the real pipeline) |
| `sentinel.storage` | Dataset/experiment-result JSON (de)serialization | — |
| `sentinel.reporting` | Markdown/JSON/HTML report rendering from a `ReportBundle` | — |
| `sentinel.observability` | Structured logging, Prometheus-compatible metrics (no-op if unavailable) | — |
| `sentinel.cli` | Typer app wiring every command above | everything (it's the integration point) |

The dependency direction is deliberately one-way: `schemas` is the shared vocabulary, `retrieval`/
`generation` are independent and only meet inside `adapters`, and `evaluation`/`diagnosis`/`repair`
form a pipeline that never reaches back into `retrieval`/`generation` internals — they only see
`RetrievalResult`/`GenerationOutput` schemas. This is what ADR-001 and ADR-002 formalize.

## The adapter pattern (why Sentinel isn't hard-wired to itself)

`sentinel.adapters.base.RAGSystem` is the only contract the rest of the toolkit depends on:
`ingest(documents)`, `retrieve(query) -> RetrievalResult`, `generate(query, retrieval) ->
GenerationOutput`, plus an optional `full_ranking(query)` used by diagnosis to find the true rank
of a missed relevant document. `ReferenceRAGAdapter` is one real implementation (BM25 + hashing
dense + RRF + optional rerank/MMR/query-rewrite + pluggable generation provider);
`DeterministicTestAdapter` is a canned-output stub used to test Sentinel's own evaluation
machinery in isolation. Evaluating a third-party RAG system means writing one more `RAGSystem`
implementation that calls out to that system — no other code changes.

## Embeddings

Default: `HashingEmbeddingProvider` — a **signed feature-hashing vectorizer** over word
uni/bigrams and character 3-5-grams (a real, classical IR technique, not a neural model),
fully offline and deterministic. It is honestly weaker than a trained sentence encoder at true
semantic (paraphrase/synonym) matching — it works largely by lexical/sub-word overlap. This is
why several experiments (`docs/experiments/01`, `04`) show dense retrieval underperforming or
tying with BM25: the "dense" signal here is not a semantic embedding in the neural sense.
`SentenceTransformerEmbeddingProvider` (optional dependency, `pip install sentinel-rag[embeddings]`)
plugs in a real model; it is not the default because it requires downloading model weights (not
reproducible/offline-safe for CI) and is non-deterministic across hardware/library versions.

## Generation providers

`DeterministicLocalProvider` is an **extractive** answerer: it scores evidence-chunk sentences by
lexical overlap with the query, refuses below a configurable evidence-coverage threshold, and
stitches the top sentences into an answer with per-sentence citations. It requires no API key, no
network access, and is bit-for-bit reproducible — the entire CI and default-benchmark path uses it.
It is explicitly **not** a language model: it cannot paraphrase, synthesize across chunks, or be
"convinced" by embedded instructions, which is why it is structurally near-immune to
instruction-following prompt injection (see `docs/experiments/08`) while still being vulnerable to
attacks that only need to get malicious *content* extracted (Experiment 7's poisoning curve).
`OpenAIProvider`/`AnthropicProvider` are real, fully-implemented adapters gated behind an API key
env var; they are not called anywhere in tests or CI.

## Evaluation layering

Every metric surfaces a `method` field (`"mechanical" | "llm_judge" | "unavailable"`) so a report
never conflates a cheap lexical proxy with a validated judgment:

- **Mechanical**: `sentinel.metrics.retrieval` (Recall/Precision/HitRate/MRR/nDCG@k, exact),
  `sentinel.metrics.citation` (lexical-overlap "does this chunk support this claim" proxy),
  `sentinel.evaluation.faithfulness.MechanicalFaithfulnessJudge` (same proxy applied per-claim
  against all evidence), `sentinel.evaluation.answer_relevance` (lexical overlap vs. reference).
- **LLM-judge**: `sentinel.evaluation.faithfulness.LLMFaithfulnessJudge` — interface and versioned
  prompt (`sentinel.generation.prompts.JUDGE_*`) are implemented; the actual model call is an
  explicit `NotImplementedError` extension point (see `docs/evaluation/faithfulness.md`) rather
  than a half-wired call that would silently produce wrong numbers.
- **Unavailable**: any metric with no cases producing a value (e.g., citation metrics on a fully-
  refused dataset) reports `value=None, method="unavailable"` rather than defaulting to 0.

## Retrieval-metric granularity

`sentinel.evaluation.evaluator._retrieved_and_relevant_ids` matches at **document granularity**
(retrieved chunk -> its `document_id` vs. `relevant_document_ids`) unless a case supplies explicit
`relevant_chunk_ids`. This is deliberate: chunk ids are `"{document_id}::chunk{position}"`, so
changing `chunk_size` changes chunk ids, and chunk-granularity ground truth captured under one
chunk_size silently stops matching under another. Document granularity stays meaningful across the
chunk-size sweep in Experiment 5. See `docs/evaluation/retrieval-metrics.md`.

## Storage

v1 ships **local JSON files** for datasets (`datasets/**/*.json`) and experiment results
(`experiments/results/*.json`) — zero-config, diffable, and sufficient for the golden-dataset scale
this project targets. `docker-compose.yml` provisions a PostgreSQL+pgvector service for a
production deployment wiring a real vector-backed `RAGSystem` adapter, but the shipped
`ReferenceRAGAdapter`/CLI do not require it — see ADR-003 for the reasoning. Swapping in Postgres
storage means implementing the same load/save functions in `sentinel.storage` against a DB
connection instead of a filesystem path.

## Observability

`sentinel.observability.logging` emits structured JSON logs with no raw prompt/evidence content at
INFO+ (see `docs/security/threat-model.md`). `sentinel.observability.metrics` defines
Prometheus-compatible `Counter`/`Histogram` objects that no-op if `prometheus_client` isn't
installed, so the core library has no hard dependency on it. OpenTelemetry tracing spans
(`sentinel.observability.tracing`, per spec section 26/35) are a stated v1.1 addition — logging and
metrics ship in v1; a wired-up OTel exporter does not, to avoid a heavy dependency for a benchmark
tool most users will run locally/in CI rather than as a long-running service.

## Known v1 limitations (see also each experiment's own Limitations section)

- No committed web UI (spec section 28 marks it optional; the CLI + generated HTML report are the
  v1 UI surface).
- LLM-judge faithfulness is an interface + versioned prompt, not a wired model call (see above).
- Conflict detection (`sentinel.retrieval.conflict`) is a standalone signal, not yet consumed by
  diagnosis/repair (Experiment 9).
- Acceptance-criteria selection in `sentinel repair run` is not failure-type-aware (Experiment 10).
- OpenTelemetry tracing is not wired up; structured logging + Prometheus-compatible metrics are.
- `SentenceTransformerEmbeddingProvider` and a real cross-encoder `Reranker` are implemented as
  extension points but not exercised by the default benchmark (they require extra dependencies /
  model downloads that would break offline CI reproducibility).
