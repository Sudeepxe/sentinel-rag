# Experiment 3: Effect of Reranking

**Status:** run against `datasets/golden/v1.json`. Regenerate with `python scripts/run_all_experiments.py`.

## Hypothesis

Reranking a wider candidate pool (`rerank_top_n=20`) with `LexicalOverlapReranker` before
truncating to `top_k=5` will improve MRR/nDCG over hybrid RRF fusion alone.

## Method

`hybrid_rrf` with `use_reranker=True, rerank_top_n=20` vs. plain `hybrid_rrf`, same dataset/config
otherwise.

## Results

| config | recall@5 | MRR | nDCG@5 | latency (ms) |
|---|---|---|---|---|
| hybrid RRF | 1.000 | 0.8270 | 0.9557 | 0.110 |
| hybrid RRF + reranker | 1.000 | 0.8270 | 0.9557 | 0.122 |

## Interpretation

**No measurable benefit** from reranking on this dataset — every metric is bit-for-bit identical,
and latency is measurably worse (+11%). This is an honest negative result with a clear mechanical
explanation: `LexicalOverlapReranker` computes Jaccard token overlap between the query and each
candidate chunk, which is highly correlated with the BM25 signal already feeding the RRF fusion.
Reranking with a *redundant* signal cannot change an ordering that signal already agrees with.

This is exactly the kind of result the repair engine's acceptance gate (`sentinel repair run`) is
built to catch: a plausible-sounding repair ("enable reranking") that a naive report might list as
"applied" without checking whether it actually helped. Sentinel-RAG's controlled-experiment
requirement means this repair would be **rejected** by `min_relative_improvement` on any
ranking metric.

## Limitations

- A cross-encoder reranker (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`) provides an
  *independent* relevance signal (full query-document attention) rather than a lexical proxy, and
  would very plausibly show a different result. The reranker abstraction
  (`sentinel.retrieval.reranker.Reranker`) is designed for exactly this swap; it is not implemented
  in v1 to avoid a heavy model dependency in the default install — see `docs/architecture/overview.md`.
- As in Experiments 1-2, recall@5 is already at ceiling, so reranking has no room to show a
  recall improvement even if the ranking within top_k shifted.
