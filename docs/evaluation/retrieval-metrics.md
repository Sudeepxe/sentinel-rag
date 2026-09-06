# Retrieval Metrics: Definitions and Granularity

## Metrics implemented (`sentinel.metrics.retrieval`)

All are computed mechanically (no LLM involved), from a ranked list of retrieved ids and a set of
relevant ids:

- **Recall@k**: fraction of relevant items found in the top k.
- **Precision@k**: fraction of the top k that are relevant.
- **Hit Rate@k**: 1.0 if any relevant item is in the top k, else 0.0.
- **MRR**: reciprocal rank of the first relevant item (0 if none found).
- **nDCG@k**: discounted cumulative gain over the top k, normalized by the ideal ordering. A
  relevant id can only contribute gain once even if it appears more than once in the retrieved list
  (see the granularity note below for why duplicates can occur) — this was a real bug caught by
  the property-based test suite (`tests/property/test_retrieval_metric_bounds.py`), fixed by
  de-duplicating within `ndcg_at_k`.

## Granularity: document vs. chunk

A `DatasetCase` can specify ground truth at two granularities:

- `relevant_document_ids` (document-level) — the common case.
- `relevant_chunk_ids` (chunk-level) — for cases where a document has multiple chunks and only a
  specific one is authoritative (e.g., conflicting-evidence cases with two versions of a document).

`sentinel.evaluation.evaluator._retrieved_and_relevant_ids` uses chunk-level matching **only when
`relevant_chunk_ids` is non-empty**; otherwise it matches at document granularity by mapping each
retrieved chunk to its `document_id`. This is a deliberate choice, not an oversight: chunk ids are
derived from `chunk_size`/`chunk_overlap` (`"{document_id}::chunk{position}"`), so ground truth
captured at one chunking configuration silently stops matching under a different one — exactly the
scenario `docs/experiments/05-chunk-size-sensitivity.md` sweeps. Document-granularity ground truth
stays valid across that entire sweep.

**Consequence:** Precision@k can slightly overcount "irrelevant" hits when multiple chunks from the
*same* relevant document appear in the top k (each is a distinct chunk id but the same document),
and duplicate document ids in a retrieved list are a real, expected occurrence this metric suite
handles (see the nDCG de-duplication above) rather than assuming won't happen.

## Why recall@5 is 1.0 across several experiments

Experiments 1-5 (`docs/experiments/`) mostly show `recall_at_5 = 1.0` regardless of retrieval
strategy, chunk size, or query rewriting. This is a real, honestly-reported ceiling effect of the
golden dataset's small per-case corpora (median ~3 documents), not evidence that those knobs don't
matter in general. Experiment 6 (retrieval depth) is the one sweep in this set that *does* find
recall variation, because `top_k` directly controls whether that small corpus's relevant document
fits in the window at all.

## What these metrics do NOT tell you

Retrieval metrics say nothing about whether the *generated answer* actually used the retrieved
evidence correctly — that's the job of citation and faithfulness metrics
(`docs/evaluation/faithfulness.md`). A system can have perfect recall@5 and still hallucinate,
misattribute a citation, or answer an unanswerable question — all three occur in the golden-dataset
baseline run (see `reports/latest.md`'s failure taxonomy section).
