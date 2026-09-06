# ADR-003: Why a Deterministic Local Generation Provider

## Context

The spec requires that CI and the default benchmark run without any paid API key, that results be
reproducible, and — critically — that no fabricated or fake model output ever be presented as real.
A generation provider is needed that satisfies all three simultaneously.

## Decision

Ship `DeterministicLocalProvider`: a genuinely deterministic **extractive** answerer (selects and
stitches the highest lexical-overlap sentences from retrieved evidence, with a configurable
refusal threshold) rather than any kind of mocked/templated "pretend LLM." It is labeled
`is_deterministic_local=True` on every `GenerationOutput` it produces, and every report/doc that
surfaces its numbers states plainly that it is not a language model. `OpenAIProvider` and
`AnthropicProvider` are real, fully-implemented adapters behind the same `GenerationProvider`
interface, gated on an environment variable API key, never invoked in tests/CI.

## Alternatives Considered

- **A canned/scripted "fake LLM" that returns pre-written answers for known questions.** Rejected
  outright — this is precisely the "fabricated model output" the spec forbids, and it would only
  work for exactly the questions it was scripted for, defeating the point of an evaluation tool.
- **Require an API key and skip CI/offline support entirely.** Rejected: this would make the
  project impossible to run, test, or benchmark without a paid account, contradicting "must install
  cleanly, run tests, run local benchmark ... without paid API credentials."
- **A small local open-weight LLM (e.g., via `llama.cpp`) as the default.** Rejected for v1: adds a
  multi-GB model-weight dependency to the default install, is not perfectly reproducible across
  hardware/quantization, and is still not "no model" — it's a real (if small) LLM masquerading as
  a lightweight default, which risks the same "is this a real result" ambiguity the spec is
  concerned about. Left as a natural future extension via the existing `GenerationProvider`
  interface, not implemented in v1.

## Consequences

- Every number in the committed `reports/latest.*` and `docs/experiments/*.md` files that comes
  from the deterministic provider is bit-for-bit reproducible from a clean checkout with zero
  configuration.
- Generation-quality metrics (faithfulness, answer relevance) measured against this provider are a
  **floor**, not representative of a real LLM's behavior — this is repeated at every surface where
  it matters (README, architecture doc, every relevant experiment write-up) rather than stated
  once and forgotten.
- Security/attack results against this provider specifically cannot demonstrate instruction-
  following-based prompt-injection vulnerability, since the provider has no instruction-following
  capacity to exploit (Experiment 8) — this is a real, load-bearing limitation of the default
  benchmark, not a strength to advertise.
