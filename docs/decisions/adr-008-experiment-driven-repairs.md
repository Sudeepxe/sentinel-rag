# ADR-008: Why Repair Proposals Are Experiment-Driven, Never Auto-Applied

## Context

Once a failure is diagnosed with high confidence (e.g., "relevant document ranked below top-k"),
it's tempting to have the system automatically apply the obvious-looking fix ("increase top_k") and
report success. Experiment 10 demonstrates concretely why this would be dishonest: of 7
plausible, correctly-diagnosed repair proposals generated against a real weak baseline, only 1
actually cleared a real acceptance bar when measured — the other 6 were reasonable-sounding changes
that either didn't help enough or introduced a latency regression.

## Decision

`sentinel.repair.engine.RepairEngine.suggest` only ever returns `RepairProposal` objects — a
proposed config delta, rationale, expected effect, and risk statement. Nothing in the codebase
applies a proposal automatically. Accepting a repair requires running it as a real controlled
experiment (`ExperimentRunner.run` on the proposal's `experiment_config`) and passing it through
`sentinel.repair.acceptance.evaluate_acceptance` against explicit, configurable
`AcceptanceCriteria` (minimum relative improvement per metric, max latency regression, a list of
metrics that must never regress). `sentinel repair run` is the CLI command that performs this whole
baseline-vs-candidate-vs-decision loop and exits non-zero if the repair is rejected.

## Alternatives Considered

- **Auto-apply the highest-confidence repair and report the diagnosis confidence as the "fix
  confidence."** Rejected: diagnosis confidence measures how sure the engine is about *what's
  wrong*, not whether a specific proposed change will measurably help — Experiment 10 shows these
  can diverge sharply (0.9-confidence diagnoses whose "obvious" fix still failed acceptance).
- **Apply repairs automatically but allow a human to revert.** Rejected for v1: this still risks a
  window where a report reflects an unvalidated change, and "revert if it turns out wrong" inverts
  the burden of proof the spec asks for (repairs must be validated *before* being presented as
  improvements).

## Consequences

- Every "the system was repaired" claim in this project's docs is backed by a specific accepted
  `RepairDecision` with real before/after numbers (Experiment 10), never a confidence score alone.
- `AcceptanceCriteria` thresholds are per-deployment configuration
  (`configs/experiments/acceptance_default.yaml`), not hard-coded, per the spec's explicit
  requirement.
- This adds operational friction (someone/something must run and evaluate the candidate experiment
  before a repair takes effect) — an intentional tradeoff of safety over convenience, and a known
  gap (acceptance-criteria routing by failure type, noted in Experiment 10's limitations) is left
  for v1.1 rather than papered over with a one-size-fits-all default that would look complete but
  behave incorrectly for refusal-focused repairs.
