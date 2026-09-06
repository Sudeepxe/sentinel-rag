# Experiment 9: Conflicting Evidence Detection

**Status:** run against the 4 `conflicting_evidence` golden-dataset cases. Regenerate with
`python scripts/run_all_experiments.py`.

## Hypothesis

`sentinel.retrieval.conflict.detect_conflicts` (a deterministic heuristic: flags chunk pairs from
different documents with high token overlap but differing numeric values or polarity terms) will
catch clear numeric-value conflicts (the two competing SLA documents) but may miss conflicts
expressed through different phrasing rather than a differing number in a similar sentence.

## Method

For each of the 4 `conflict-*` cases, ran the real pipeline (hybrid_rrf, top_k=5,
deterministic_local), then ran `detect_conflicts` over the retrieved chunks.

## Results

| case | conflicts detected | citation_precision | answer_relevance | refused |
|---|---|---|---|---|
| conflict-001 (SLA uptime %, 2023 vs 2025) | **1** | 1.000 | 0.368 | no |
| conflict-002 (SLA credit cap, 2023 vs 2025) | **1** | 1.000 | 0.267 | no |
| conflict-003 (retention policy vs. unapproved draft) | 0 | 1.000 | 0.128 | no |
| conflict-004 (outage duration vs. forum rumor) | 0 | 1.000 | 0.089 | no |

## Interpretation

The hypothesis is confirmed exactly: `detect_conflicts` **catches both SLA-document cases**
(conflict-001, conflict-002), where two documents share heavy lexical overlap ("Enterprise tier
guarantees ... monthly uptime ... service credit") but disagree on the actual numbers (99.9% vs.
99.95%; 50% vs. 100% cap) — precisely the pattern the heuristic is built to find (numeric
divergence + high subject-overlap threshold). It **misses both non-SLA cases**: the retention
draft-vs-policy conflict and the outage-duration-vs-forum-rumor conflict use different vocabulary
and sentence structure to express the disagreement (a proposal describing itself as "not approved
or implemented" vs. a policy stating a retention period in months; a postmortem stating "47-minute"
vs. a forum post saying "almost 3 hours") — their token-overlap falls below the 0.5 subject-overlap
threshold required to even attempt a numeric comparison, so `detect_conflicts` correctly (by its
own conservative design) declines to flag them rather than guessing.

The system still answered all 4 cases correctly per their `reference_answer` (using the
higher-authority/more-recent document), because that judgment is encoded in each document's
`authority` and `timestamp` metadata and surfaced through the extractive generator's evidence
selection — not because conflict *detection* drove the answer choice. In this v1, conflict
detection and answer-arbitration are **separate, not yet wired together**: detection surfaces a
signal for a report/diagnosis to flag, but does not (yet) change which document the generator
prefers. That wiring is listed as a v1.1 improvement (see `docs/architecture/overview.md#limitations`).

## Limitations

- `detect_conflicts`'s 0.5 subject-overlap threshold is a precision-favoring design choice (see
  `sentinel/retrieval/conflict.py`): it will always miss conflicts phrased in dissimilar language,
  by design, to avoid false-positiving on merely-different documents. This experiment's 2-of-4
  detection rate is a direct, expected consequence of that choice, not a bug.
- n=4 cases is too small to report a meaningful detection rate as a percentage; the two hit/miss
  pairs are described qualitatively above instead of as a misleading "50%" statistic.
- Conflict detection output is not yet consumed by the diagnosis or repair engines (e.g., there is
  no `CONFLICTING_EVIDENCE`-triggered repair proposal in the current catalog); it is currently a
  standalone signal, surfaced via `sentinel diagnose`-adjacent tooling for a human or a future
  automated consumer.
