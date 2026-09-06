# ADR-004: Why Multiple Evaluation Layers (Mechanical + LLM-Judge)

## Context

"Faithfulness" and "citation correctness" are semantic judgments. The two obvious ways to compute
them — lexical overlap heuristics, or an LLM judge — have opposite failure modes: lexical overlap
under-counts valid paraphrases and over-counts coincidental keyword matches; an LLM judge is
expensive, non-deterministic, prompt-sensitive, and can share blind spots with the model being
evaluated (self-preference bias). Picking only one and presenting it as "the" faithfulness score
would misrepresent its reliability.

## Decision

Implement both as explicit, separately-labeled layers behind a common
`sentinel.evaluation.faithfulness.FaithfulnessJudge` interface:
`MechanicalFaithfulnessJudge` (lexical overlap, `is_llm_judge=False`, always available, free) and
`LLMFaithfulnessJudge` (real model call, `is_llm_judge=True`, requires a configured provider).
Every `MetricValue` in a report carries a `method` field (`"mechanical" | "llm_judge" |
"unavailable"`) so a reader — human or CI gate — never mistakes one for the other.
`compute_judge_disagreement` is provided for the case where multiple judges run, to surface
disagreement rather than silently averaging it away.

## Alternatives Considered

- **LLM-judge only.** Rejected: makes faithfulness evaluation impossible offline/in CI, and the
  spec explicitly requires a deterministic path.
- **Mechanical only, presented without qualification as "faithfulness."** Rejected: this would
  overstate what a lexical-overlap heuristic can actually detect (see
  `docs/evaluation/faithfulness.md` for concrete false-positive/negative examples) and violates the
  spec's requirement to distinguish mechanically-measured from model-judged metrics.
- **A single blended score averaging both layers.** Rejected: blending hides exactly the
  disagreement information that's most useful for deciding whether to trust a given case's score.

## Consequences

- CI can gate on `faithfulness (mechanical)` with zero cost/API dependency; a nightly or release
  job can additionally run the LLM-judge layer where a key is configured, and both results appear
  side-by-side rather than one silently replacing the other.
- `LLMFaithfulnessJudge.judge()` currently raises `NotImplementedError` with a clear message
  pointing at the documented contract — an explicit extension point rather than a half-wired call
  that would produce a plausible-looking but meaningless number. Wiring in a real judge call is
  listed as a v1.1 task in `CHANGELOG.md`, not silently faked.
