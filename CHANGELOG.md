# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - Unreleased

### Added

- Initial public release of Sentinel-RAG.
- Provider-agnostic RAG adapter interface (`ReferenceRAGAdapter`,
  `DeterministicTestAdapter`) with BM25, hashing-based dense retrieval,
  hybrid fusion (RRF), and MMR diversification.
- Deterministic local embedding and generation providers requiring no
  external API keys, plus pluggable OpenAI/Anthropic provider interfaces.
- Retrieval, citation, faithfulness, and refusal metrics with mechanical
  (non-LLM) and LLM-judge evaluation layers, explicitly labeled.
- Failure taxonomy and evidence-backed root-cause diagnosis engine.
- Rule-based repair engine with experiment-gated acceptance criteria.
- Reproducible experiment framework with bootstrap confidence intervals.
- Adversarial testing framework covering prompt injection, retrieval
  poisoning, context flooding, and citation manipulation, with a
  SAFE/PARTIAL/FAILED/UNKNOWN attack-outcome taxonomy.
- 50-case golden evaluation dataset spanning 16 categories.
- CLI (`sentinel ...`) covering dataset validation, evaluation, attacks,
  diagnosis, repair, experiments, benchmarking, and reporting.
- Optional FastAPI service exposing the same operations over HTTP.
- GitHub Actions CI with PR/nightly/release lanes and a regression gate.
- Architecture docs, ADRs, and a threat model.

### Known limitations

See `README.md#limitations` and `docs/architecture/overview.md` for the
full, current list (LLM-judge evaluation requires an external API key and
is disabled by default in CI; no committed web UI in v1; pgvector backend
is documented but the shipped default is a local vector index).
