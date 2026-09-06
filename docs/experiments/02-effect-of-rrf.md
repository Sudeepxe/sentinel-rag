# Experiment 2: Effect of Reciprocal Rank Fusion

**Status:** run against `datasets/golden/v1.json`. Regenerate with `python scripts/run_all_experiments.py`.

## Hypothesis

Fusing BM25 and dense rankings via RRF will not regress below the better of the two individual
strategies, and may improve ranking quality where the two signals disagree.

## Method

Compare `hybrid_rrf` (this experiment's subject) against the `dense` and `bm25` single-strategy
runs from Experiment 1, same dataset/config otherwise.

## Variables

Fusion (on/off) — "off" meaning single-strategy dense or BM25.

## Controls

Same as Experiment 1.

## Results

| config | MRR | nDCG@5 |
|---|---|---|
| dense only | 0.8176 | 0.9488 |
| BM25 only | 0.8270 | 0.9557 |
| hybrid (RRF) | 0.8270 | 0.9557 |

## Interpretation

RRF fusion **does not regress** relative to the stronger individual strategy (BM25) — it exactly
matches it on this dataset. It also does not exceed BM25 here. This is the expected outcome when
one component ranker (BM25) is already near-ceiling and the other (dense/hashing) never
outranks it on any case in the set: RRF has no disagreement to arbitrate in the relevant document's
favor beyond what BM25 already provides. The practical takeaway from this specific measurement is
narrower than "RRF helps": on this dataset, hybrid's value-add over BM25-alone was not measurable;
its value proposition (recovering cases where lexical match fails but semantic similarity succeeds,
or vice versa) is not exercised because BM25 alone already ranks correctly on all 53 cases.

## Limitations

- This experiment cannot demonstrate RRF's benefit without cases where BM25 and dense
  meaningfully *disagree* on ranking. The `sem-005` golden case (terminology-mismatch paraphrase)
  was designed to stress exactly this, but at the current corpus size (4 documents) both strategies
  still surface the right document within top_k=5 regardless. A larger, harder adversarial-paraphrase
  slice would make this comparison more informative — tracked as a v1.1 dataset expansion, not
  implemented here to avoid inflating the dataset with cases hand-tuned to flatter one algorithm.
- With a real neural embedding provider instead of the hashing baseline, dense retrieval would
  likely diverge more from BM25 on paraphrased queries, giving RRF more to fuse.
