# Experiment 1: Dense vs. BM25 vs. Hybrid Retrieval

**Status:** run against `datasets/golden/v1.json` (53 cases, sentence-transformers not installed —
dense = `HashingEmbeddingProvider`). Regenerate with `python scripts/run_all_experiments.py`.

## Hypothesis

Hybrid (BM25 + dense, RRF-fused) retrieval will match or beat either single strategy alone, since
it can recover from either strategy's blind spots (BM25 misses paraphrase/synonym matches; a
lexically-flavored hashing embedding can still miss cases where BM25's exact term match is
stronger).

## Method

Three `RetrievalConfig`s (`strategy: dense`, `strategy: bm25`, `strategy: hybrid_rrf`), identical
otherwise (`top_k=5`, `chunk_size=400`, no reranker/MMR/query-rewrite), each run via
`sentinel evaluate` over the full golden dataset with the deterministic local generation provider.

## Variables

Retrieval strategy only.

## Controls

Dataset, chunk size, top_k, generation provider/config, seed (1337) all held fixed.

## Metrics

| strategy | recall@5 | precision@5 | MRR | nDCG@5 | latency (ms) |
|---|---|---|---|---|---|
| dense (hashing) | 1.000 | 0.567 | 0.8176 | 0.9488 | 0.112 |
| BM25 | 1.000 | 0.567 | 0.8270 | 0.9557 | 0.043 |
| hybrid (RRF) | 1.000 | 0.567 | 0.8270 | 0.9557 | 0.110 |

## Interpretation

recall@5 and precision@5 are **identical across all three strategies** — an honest artifact of
dataset scale, not a finding about retrieval quality: golden-set cases carry small per-case corpora
(2-96 documents, median ~3), so at `top_k=5` most strategies already surface the relevant document
somewhere in the top 5. MRR and nDCG@5, which are sensitive to *rank*, do differentiate: BM25 and
hybrid both rank the relevant document slightly higher on average than dense-only (MRR 0.827 vs.
0.818), because the golden set's questions frequently share exact terminology with the source
document (a realistic property of internal-knowledge-base Q&A) — exactly BM25's strength. Hybrid
matches BM25 here rather than exceeding it, because RRF-fusing a weaker dense signal with a
stronger BM25 signal does not hurt, but with only two component rankers and BM25 already
near-ceiling on this set, there is no additional signal left for hybrid to recover.

BM25 is also **~2.5x faster** than dense or hybrid (0.043ms vs. ~0.11ms) since it skips the
embedding/cosine-similarity step entirely — a real, measurable cost difference worth weighing
against the ranking-quality gain hybrid/BM25 show over dense-only.

## Limitations

- The embedding provider under test is `HashingEmbeddingProvider` (a deterministic offline
  hashing-trick vectorizer, not a trained neural encoder — see
  `docs/architecture/overview.md#embeddings`). A real sentence-transformer model would likely show
  a different (probably more favorable to dense) picture, especially on paraphrase-heavy queries;
  rerun with `pip install sentinel-rag[embeddings]` and a `SentenceTransformerEmbeddingProvider` to
  compare.
- recall@5 saturating at 1.0 for all three strategies means this experiment, on this dataset, does
  **not** actually stress-test recall differences — see Experiment 6 (retrieval depth) for a
  setting (`top_k=1`) where strategy and depth do produce measurable recall differences.
- n=53 cases; per-metric bootstrap confidence intervals were not computed for this specific
  three-way comparison (see `sentinel compare` for pairwise CIs between any two saved experiment
  results).
