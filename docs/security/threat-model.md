# Threat Model

Sentinel-RAG has two distinct security surfaces: (1) Sentinel-RAG itself, as a piece of software
with dependencies, config, and secrets; and (2) the RAG systems Sentinel-RAG is used *to test*,
which is the actual subject of the adversarial-testing feature set. This document covers both.

## Assets

| Asset | Description | Where it lives |
|---|---|---|
| Knowledge base documents | Corpus content given to a RAG system under test | `DatasetCase.documents`, external systems |
| User queries | Questions posed to a RAG system | Dataset files, CLI args |
| Model outputs | Generated answers, citations | `GenerationOutput`, logs, reports |
| Provider credentials | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Environment variables only |
| Evaluation datasets | Golden/adversarial test cases | `datasets/**/*.json` |
| Experiment/attack reports | Metrics, failure records, attack outcomes | `experiments/results/`, `reports/` |

## Threats and mitigations

### 1. Prompt injection (direct and indirect)

**Threat:** a document in the retrieved context contains an instruction intended to override the
system prompt or user intent.
**Mitigation (in Sentinel):** the adversarial suite (`sentinel attack run`) exists specifically to
measure this against any configured provider; `ANSWER_SYSTEM_PROMPT` explicitly instructs a real
LLM provider to treat evidence as data, not instructions.
**Residual risk:** Sentinel cannot make an external LLM provider robust to injection — it can only
measure susceptibility. The deterministic local provider is structurally immune (no instruction-
following capacity) but this is a property of that one baseline, not a general defense (see
`docs/experiments/08-prompt-injection-robustness.md`).

### 2. Data / credential exfiltration via generated answers

**Threat:** a malicious document instructs the system to reveal a synthetic "credential" or
internal marker in its answer.
**Mitigation:** `sentinel.attacks.generator` uses only synthetic markers
(`SENTINEL-TEST-SECRET-...`), never real secrets; `AttackClassifier` flags leakage by literal
canary match, giving an unambiguous, auditable success/failure signal.
**Residual risk:** none to Sentinel's own operators, by construction — no real secret is ever
placed in a test fixture. A RAG system found vulnerable via this suite could, in production, leak
*real* secrets if operators embed them in retrievable documents; that is a finding about the system
under test, which the report is designed to surface clearly.

### 3. Retrieval poisoning

**Threat:** an attacker injects documents engineered to rank highly for common queries, displacing
legitimate evidence (measured concretely in `docs/experiments/07-adversarial-document-poisoning.md`
— a 5% poisoning rate collapsed recall@5 from 1.0 to 0.0 in the reference pipeline's default
config).
**Mitigation:** the poisoning-curve experiment gives operators a way to measure their own system's
degradation curve before an incident, not just react after one. `Document.authority` and
freshness-policy support (`sentinel.retrieval.freshness`) are stated tools for reducing (not
eliminating) this risk, by weighting trusted/recent sources higher.
**Residual risk:** the reference pipeline has no dedicated anomaly/outlier detection for
suspiciously query-similar documents; this is a real, documented gap, not a solved problem.

### 4. Benchmark / evaluator manipulation

**Threat:** a dataset or config is silently modified to make a system look better than it is
(e.g., tuning chunk boundaries to align exactly with expected answers, or hand-picking easy cases).
**Mitigation:** `datasets/golden/README.md` documents the overfitting risk explicitly;
`sentinel dataset validate` schema-checks every case; experiment results record `config_hash`,
`dataset_version`, and `git_commit` so a result can be tied to the exact inputs that produced it.
**Residual risk:** Sentinel cannot detect a maliciously-crafted dataset from its schema alone — a
dataset that is internally consistent but unrepresentative would pass validation. Human review of
new dataset cases (and diversity/category-coverage checks like `sentinel dataset validate`'s
per-category counts) is the primary mitigation.

### 5. Secret leakage from Sentinel-RAG itself

**Threat:** an API key or other credential ends up in a log, report, or committed file.
**Mitigation:** `.env` is git-ignored; `.env.example` documents required variables without values;
`sentinel.observability.logging` explicitly does not log raw prompts/evidence/canaries at INFO+;
CI runs `bandit` on every PR; provider adapters read keys only from environment variables, never
from CLI arguments (which would appear in shell history/process lists) or config files.
**Residual risk:** a user could still paste a key into a dataset `notes` field or a config file by
mistake; this is a user-error class of risk mitigated by documentation, not code.

### 6. Malformed / adversarial API responses from a real provider

**Threat:** a configured OpenAI/Anthropic provider returns a malformed, truncated, or unexpectedly
structured response.
**Mitigation:** `sentinel.generation.base` defines explicit `ProviderTimeoutError`,
`ProviderMalformedResponseError`, `ProviderRateLimitError`; `ExperimentRunner.run` catches any
exception per-case and records it as a `CaseEvaluation.error`, never silently treating a crashed
case as a score of zero or missing data (see `tests/unit/test_failure_injection.py`).

## Out of scope for v1

- Network-level threats to a deployed FastAPI service (TLS termination, DDoS) — deployment-specific
  and left to standard infrastructure practice; `sentinel serve` (if run) is intended for
  local/trusted-network use in v1, not public exposure without a reverse proxy and auth layer.
- Supply-chain attacks on third-party dependencies beyond what `pip-audit`/Dependabot-style
  scanning catches in CI.
- Multi-tenant isolation (Sentinel-RAG is a single-operator evaluation tool in v1, not a hosted
  multi-customer service).

## Responsible use

See `SECURITY.md` for the authorization requirement on the adversarial toolkit: only test systems
you own or are explicitly authorized to test.
