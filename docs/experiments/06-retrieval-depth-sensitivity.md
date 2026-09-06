# Experiment 6: Retrieval Depth (top_k) Sensitivity

**Status:** run against `datasets/golden/v1.json`. Regenerate with `python scripts/run_all_experiments.py`.

## Hypothesis

Recall should increase monotonically with `top_k` and plateau once `top_k` exceeds the number of
documents most cases need; precision should decrease as `top_k` grows past the true relevant-set
size, since irrelevant documents fill the extra slots.

## Method

`top_k` in `{1, 2, 3, 5, 10}`, `hybrid_rrf`, otherwise identical config. This is the one ablation
in this set that **is** meaningfully stressed by the golden dataset's per-case corpus sizes.

## Results

| top_k | recall@k | precision@k | MRR | latency (ms) |
|---|---|---|---|---|
| 1 | 0.811 | 0.774 | 0.7736 | 0.095 |
| 2 | 0.981 | 0.604 | 0.8208 | 0.110 |
| 3 | 1.000 | 0.582 | 0.8270 | 0.107 |
| 5 | 1.000 | 0.567 | 0.8270 | 0.109 |
| 10 | 1.000 | 0.559 | 0.8270 | 0.117 |

## Interpretation

This confirms both halves of the hypothesis with real, clean numbers:

- **Recall climbs sharply from top_k=1 to top_k=3** (0.811 -> 0.981 -> 1.000) then **plateaus** —
  every case in the golden set has its relevant document within the top 3 candidates under hybrid
  retrieval, so top_k beyond 3 buys nothing further.
- **Precision falls monotonically** (0.774 -> 0.604 -> 0.582 -> 0.567 -> 0.559) as `top_k` grows,
  because the number of truly-relevant documents per case is usually 1 (occasionally 2), so each
  additional slot beyond that is, by construction, an irrelevant document diluting precision.
- MRR is flat from top_k=3 onward (0.827) because MRR only depends on the rank of the *first*
  relevant hit, which doesn't change once top_k is large enough to contain it — consistent with
  recall's plateau.
- Latency is flat (~0.10-0.12ms) across all top_k values tested — at this dataset's corpus sizes,
  scoring cost dominates over the (trivial) cost of sorting/truncating a slightly larger candidate
  list.

**Practical implication:** for a corpus shaped like this golden set, `top_k=3` captures the same
recall as `top_k=10` at meaningfully higher precision (0.582 vs. 0.559) and identical MRR — a
concrete, evidence-backed recommendation this experiment actually supports, unlike Experiments 1-5.

## Limitations

- The optimal top_k found here (3) is a property of this dataset's corpus sizes (median ~3
  documents per case) and the fact that questions are mostly single-hop with one clearly relevant
  document. Multi-hop cases (`hop-*`) or multi-document-reasoning cases (`multi-*`) that need 2+
  documents simultaneously are a minority of the set; a corpus weighted more heavily toward those
  would likely show recall still climbing at top_k=5 or beyond.
- Precision@k here uses document-granularity matching (see
  `docs/evaluation/retrieval-metrics.md`), which slightly overstates "irrelevant" hits when a
  retrieved document is topically adjacent but not the graded-relevant one.
