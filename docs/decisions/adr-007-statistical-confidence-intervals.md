# ADR-007: Why Statistical Confidence Intervals on Comparisons

## Context

A 53-case golden dataset means a single case flipping from wrong to right moves an aggregate metric
by ~1.9 percentage points. Reporting "recall improved from 0.81 to 0.86" without any sense of
whether that's a two-case fluke or a robust effect would misrepresent the strength of the evidence
— exactly the kind of unsupported claim the spec forbids ("Sentinel improves RAG by 37%" without
backing).

## Decision

`sentinel.experiments.stats.paired_bootstrap_diff` computes a genuine paired bootstrap confidence
interval from the actual per-case metric values of two runs (resampling case-level diffs, not
re-deriving anything analytically), used by `sentinel.experiments.comparison.compare_experiments`
and surfaced by `sentinel compare`. Comparisons with fewer than 5 paired cases skip the bootstrap
and say so explicitly in the comparison's `notes`, rather than reporting a CI computed from too few
points to mean anything.

## Alternatives Considered

- **Report raw percentage-point differences only**, as many benchmark scripts do. Rejected: this is
  precisely the practice the spec singles out as insufficient ("Do not rely only on raw percentage
  differences").
- **A parametric test (paired t-test) instead of bootstrap.** Rejected as the default: metric
  distributions here are bounded in [0,1] and often have many ties (e.g., recall of exactly 0 or 1
  per case), which violates t-test normality assumptions more readily than it violates bootstrap's
  much weaker assumptions. Cohen's d (`sentinel.experiments.stats.cohens_d`) is still provided as a
  secondary effect-size measure for readers who want it.

## Consequences

- Every `sentinel compare` output that includes a CI is honest about its own uncertainty; a wide CI
  spanning zero is reported as `significant: false` rather than glossed over.
- Bootstrap resampling uses a fixed seed (`1337` by default) so the CI itself is reproducible
  between runs of the same comparison, consistent with the project's overall reproducibility
  requirement.
- On the current 53-case dataset, most comparisons will have visibly wide intervals — this is
  surfaced as a real limitation of dataset size (see `docs/experiments/*.md` and
  `README.md#limitations`) rather than a shortcoming of the statistics code.
