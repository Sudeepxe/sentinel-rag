# ADR-005: Why CI Evaluation Gates

## Context

A reliability tool that doesn't apply its own discipline to itself is not credible. Retrieval,
generation, and metric code changes can silently regress recall, citation precision, or refusal
behavior without any test *failing* in the conventional sense — the code still runs, it just
answers worse. Unit tests check code correctness; they don't check quality regression.

## Decision

Add `sentinel gate --baseline <result> --candidate <result> --thresholds <config>`
(`sentinel/cli/main.py`, backed by `configs/experiments/regression_gate.yaml`), which fails
(exit code 1) if a candidate experiment result regresses beyond configured, named tolerances
relative to a baseline — e.g. `recall_at_5` dropping more than 0.03, or `attack_success_rate`
rising more than 0.05. This is wired as a distinct CI lane (`.github/workflows/nightly.yml`) run
against the committed baseline result, separate from the fast PR lint/unit-test lane.

## Alternatives Considered

- **Hard-code fixed target values** (e.g., "recall_at_5 must be >= 0.95") instead of relative
  regression thresholds. Rejected: a fixed absolute target doesn't survive legitimate dataset
  growth/changes and conflates "this dataset is hard" with "this change regressed something."
- **Only check regressions manually via `sentinel compare` before merging.** Rejected: manual
  review is exactly the kind of check that gets skipped under time pressure; automating it in CI
  is the whole point of a *gate*.

## Consequences

- Thresholds are configuration (`configs/experiments/regression_gate.yaml`), not constants buried
  in code, and are documented with the reasoning behind each number (e.g., "single-case flips
  already move a metric by ~2 points on a 53-case set").
- The gate needs a baseline `ExperimentResult` to compare against; establishing and periodically
  refreshing that baseline is an explicit operational step (`make reproduce` /
  `sentinel evaluate --config configs/experiments/baseline.yaml`), not automatic.
- A gate on a 53-case dataset is noisier than one on a 5,000-case dataset — thresholds are set
  deliberately loose (3 percentage points) to avoid false-positive CI failures from single-case
  flips, at the cost of being less sensitive to small real regressions. This tradeoff is stated
  directly in the gate config's comments rather than left implicit.
