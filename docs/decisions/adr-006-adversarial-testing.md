# ADR-006: Why Adversarial Testing Is a First-Class Component

## Context

RAG systems retrieve and inject untrusted document content directly into a generation context.
Retrieval quality and citation correctness metrics say nothing about whether a system can be
manipulated by content it retrieves — a system can score perfectly on Recall/MRR/citation
precision and still leak secrets or follow embedded instructions from a poisoned document. A
reliability tool that only measures accuracy, not security, would materially misrepresent a
system's readiness.

## Decision

Build `sentinel.attacks` as a peer package to `sentinel.evaluation`, not a bolt-on: a generator
producing real `AttackCase`s across 15 attack classes from real golden-dataset cases (synthetic
canaries, non-destructive instructions only — see `SECURITY.md`), a classifier producing one of
four outcomes (`SAFE`/`PARTIAL`/`FAILED`/`UNKNOWN`) from observed behavior, and a dedicated
retrieval-poisoning curve experiment. `sentinel attack run` is a first-class CLI command alongside
`evaluate`, and adversarial metrics (`attack_success_rate`, etc.) appear in the same report
structure as accuracy metrics rather than a separate, easy-to-skip artifact.

## Alternatives Considered

- **Treat adversarial testing as a "nice to have" appendix / separate optional tool.** Rejected:
  the spec is explicit that this is a major component, and treating it as optional is exactly how
  security testing gets skipped in real projects.
- **Only test against a real LLM provider**, since that's where instruction-following attacks
  matter most. Rejected: this would make the entire adversarial suite require a paid API key,
  contradicting the offline/CI-reproducibility requirement — instead, the suite runs against
  whatever provider is configured, with the deterministic-provider run's limitations stated
  explicitly (see ADR-003, Experiment 8) rather than skipped.

## Consequences

- Every attack outcome is classified from the RAG system's own observed output (canary leakage,
  citation/rank of the malicious chunk) — Sentinel never has to guess or invent a plausible-sounding
  vulnerability score.
- The suite honestly reports when it *cannot* measure something meaningful (instruction-following
  robustness against a provider incapable of following instructions) rather than reporting a
  flattering SAFE rate without qualification.
- `false_positive_rate` is reported as `0.0` by explicit construction (canaries are unique
  per-run synthetic strings), not as an empirically-validated property — this is stated in the
  suite's own output note, not left for a reader to misinterpret as "zero false positives, proven."
