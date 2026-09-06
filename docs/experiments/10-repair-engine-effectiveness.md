# Experiment 10: Repair Engine Effectiveness

**Status:** run against the full golden dataset with a deliberately weak baseline config.
Regenerate with `python scripts/run_all_experiments.py` or
`sentinel repair suggest` / `sentinel repair run`.

## Hypothesis

Given a deliberately weak configuration (`dense`-only retrieval, `top_k=1`, `chunk_size=1200`),
the diagnosis engine will identify real, specific failures, the repair engine will propose
plausible fixes, and the acceptance gate will correctly accept only the repairs that measurably
help without regressing other metrics — rejecting the rest, even when the underlying diagnosis was
correct.

## Method

1. Ran `configs/experiments/bad_baseline.yaml`-equivalent config (`golden_bad_baseline`: dense,
   top_k=1, chunk_size=1200, chunk_overlap=0) over the full 53-case golden dataset with diagnosis
   enabled.
2. Fed all diagnosed `FailureRecord`s into `RepairEngine.suggest`.
3. Ran each proposed repair's `experiment_config` as a candidate experiment.
4. Evaluated each baseline-vs-candidate pair against the default `AcceptanceCriteria`
   (`recall improves >= 5%`, `latency regression <= 15%`, no regression on `answer_relevance`).

## Results

Baseline failure counts: `FALSE_REFUSAL=3, WRONG_RANKING=7, MISSING_RELEVANT_CHUNK=7,
ANSWERED_UNANSWERABLE=4` (21 of 53 cases flagged).

7 repair proposals were generated; **1 was accepted**:

| repair | change | accepted | key reason |
|---|---|---|---|
| `repair-missing_relevant_chunk-*` | increase `top_k` 1 -> 2 | **YES** | recall improved +23.8%, no regressions |
| `repair-false_refusal-*` | lower refusal threshold 0.15 -> 0.10 | no | recall unchanged (+0.0%) |
| `repair-wrong_ranking-*` (reranker) | enable reranking | no | recall improved only +2.4% (< 5% bar) |
| `repair-wrong_ranking-*` (strategy) | switch to hybrid_rrf (top_k still 1) | no | recall improved only +2.4% |
| `repair-missing_relevant_chunk-*` (strategy) | switch to hybrid_rrf (top_k still 1) | no | recall improved only +2.4% |
| `repair-missing_relevant_chunk-*` (rewrite) | enable query expansion | no | recall +0.0% **and** latency regressed +25.8% (> 15% bar) |
| `repair-answered_unanswerable-*` | raise refusal threshold 0.15 -> 0.20 | no | recall unchanged (+0.0%, expected — this repair targets a different metric) |

## Interpretation

This is the clearest demonstration in the whole project of *why the acceptance gate exists*: 6 of
7 plausible, correctly-diagnosed repair proposals were **rejected** because they didn't clear the
configured improvement bar, even though several of them (switching to `hybrid_rrf`, enabling the
reranker) are individually reasonable engineering choices that a report generated without
controlled experimentation might have listed as "applied" or "recommended." Only increasing
`top_k` from 1 to 2 produced a measured improvement large enough to accept — consistent with
Experiment 6's finding that this dataset's recall climbs steeply from `top_k=1` to `top_k=3`.

Two rejected repairs are worth calling out specifically:
- The `hybrid_rrf` strategy-switch repairs improved recall by only 2.4% while **keeping
  `top_k=1`** — confirming (as in the standalone integration test,
  `tests/integration/test_repair_loop.py`) that strategy alone doesn't fix a
  retrieval-window problem; `top_k` and strategy address different failure modes and neither
  substitutes for the other.
- The query-expansion repair is a "worse than doing nothing" result: it did not improve recall at
  all *and* separately blew the latency budget — a repair that fails on two independent acceptance
  criteria simultaneously.

The `answered_unanswerable` repair (raising the refusal threshold) is correctly evaluated against
`recall_at_1`, which it was never intended to move — this is a known evaluation-scope gap: the
current CLI wiring checks every proposal against the same `min_relative_improvement` metric
(`recall_at_5`, resolved to `recall_at_1` here) regardless of which failure type it targets,
rather than routing refusal-focused repairs through refusal-focused acceptance criteria. See
Limitations.

## Limitations

- **Acceptance-criteria routing is not failure-type-aware in v1.** A refusal-threshold repair
  should ideally be judged primarily on `false_refusal_rate`/`unsafe_answer_rate`, not
  `recall_at_k` — the current CLI (`sentinel repair run`) always applies one fixed
  `AcceptanceCriteria` regardless of the repair's target failure type. The underlying
  `evaluate_acceptance` function supports arbitrary per-metric criteria
  (`configs/experiments/acceptance_default.yaml`), so a caller *can* pass refusal-specific
  criteria manually; automatic routing by `FailureType` is a stated v1.1 improvement, not
  implemented here.
- All repairs in this run target retrieval configuration; the repair catalog
  (`sentinel/repair/catalog.py`) does not yet propose generation-provider changes (e.g.,
  "switch from deterministic_local to a real LLM") even though several diagnosed failures
  (`ANSWERED_UNANSWERABLE`, in particular) are arguably better addressed by that lever.
- n=53 cases means small absolute count changes (e.g., 1 additional correct case) produce
  double-digit percentage swings; the `+23.8%` accepted-repair number represents roughly 2-3
  additional cases finding their relevant document, not a large-sample statistical effect.
