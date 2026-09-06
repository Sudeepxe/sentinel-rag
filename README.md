# Sentinel-RAG

**Reliability infrastructure for Retrieval-Augmented Generation systems.**

Sentinel-RAG is not a chatbot, a RAG demo, or a wrapper around an LLM API. It is an evaluation,
diagnosis, adversarial-testing, and repair platform for RAG systems — the kind of tool a team
running a RAG system in production needs to answer: *did retrieval find the right evidence, did
generation actually use it, is the answer supported, would we know if it wasn't, and can we prove
a fix actually helped?*

Every number in this README, in `reports/latest.md`, and in `docs/experiments/*.md` was produced
by actually running the code in this repository against the real dataset committed alongside it.
Where something can't be measured without a paid API key or isn't implemented, that is stated
explicitly rather than filled in with a plausible-looking number.

## Why Sentinel-RAG exists

RAG systems fail silently. A retriever can return the wrong document while an LLM still produces a
fluent, confident-sounding answer built from irrelevant evidence. A citation can point at a chunk
that never actually supports the claim next to it. A system can hallucinate an answer to a question
it should have refused, or refuse a question it could easily have answered. None of these failure
modes show up as an exception or a crash — they show up as a wrong answer that looks right. Most
RAG projects have no systematic way to catch this, no formal taxonomy for *why* it happened, and no
disciplined way to tell whether a proposed fix actually helped versus just moved the failure
somewhere else. Sentinel-RAG is built to close that gap.

## Problem statement

Given a RAG system (Sentinel's own reference pipeline, or an external one via a thin adapter) and a
dataset of questions with graded evidence, answer whether retrieval worked, whether generation used
the evidence faithfully, whether citations are correct, whether refusal behavior is correct, and
whether the system can be manipulated by adversarial content in its own retrieved documents — then
produce an evidence-backed diagnosis of any failure, a concrete config-level repair proposal, and a
controlled experiment proving (or disproving) that the repair helped.

## Architecture

```
Dataset -> RAG adapter -> Retrieval -> Evidence -> Generation -> Answer+Citations
    -> Evaluation -> Failure Detection -> Root Cause Diagnosis -> Repair Proposal
    -> Controlled Experiment -> Re-evaluation -> Reliability Report
```

See `docs/architecture/overview.md` for module boundaries, the adapter pattern, and every
component's real dependency graph. Eight ADRs in `docs/decisions/` explain the non-obvious
choices (why an adapter architecture, why a deterministic local provider, why repairs are never
auto-applied, etc.).

## Quickstart

```bash
git clone <this-repo-url> sentinel-rag && cd sentinel-rag
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

sentinel doctor                       # environment sanity check
sentinel dataset validate datasets/golden/v1.json
sentinel evaluate --config configs/experiments/baseline.yaml
sentinel benchmark                    # writes reports/latest.{md,json,html}
pytest tests/ -q                      # 66 tests, no API key required
```

No API key, no network access, and no GPU are required for any of the above — everything runs on
`DeterministicLocalProvider`, an offline extractive generator (see **Generation providers** below).

## Example evaluation

```bash
$ sentinel evaluate --config configs/experiments/baseline.yaml --format json
{
  "experiment_id": "exp-7449307319ff2a5d-97fd18ec",
  "metrics": {
    "recall_at_5": 1.0, "precision_at_5": 0.567, "mrr": 0.827, "ndcg_at_5": 0.956,
    "citation_precision": 1.0, "citation_recall": 1.0, "faithfulness": 1.0,
    "answer_relevance": 0.210, "latency_ms": 0.12, "estimated_cost_usd": 0.0
  },
  "failure_counts": {"FALSE_REFUSAL": 3, "ANSWERED_UNANSWERABLE": 4},
  "errors": 0
}
```

53 golden-dataset cases evaluated in ~0.06s with zero system errors; 7 real diagnosed failures
(see **Failure taxonomy** below — these are genuine, unfixed limitations of the shipped baseline,
not illustrative placeholders).

## Metrics

Every metric reports a `method` (`mechanical | llm_judge | unavailable`) so a report never
conflates a cheap proxy with a validated judgment — see `docs/architecture/overview.md#evaluation-layering`.

- **Retrieval** (`sentinel.metrics.retrieval`): Recall@k, Precision@k, Hit Rate@k, MRR, nDCG@k.
- **Citation** (`sentinel.metrics.citation`): precision/recall of per-claim citations, lexical
  support scoring, unsupported-claim detection.
- **Faithfulness** (`sentinel.evaluation.faithfulness`): mechanical lexical-overlap proxy
  (always available) + an LLM-judge interface with a versioned prompt (real model call not wired
  in — see `docs/evaluation/faithfulness.md`).
- **Refusal** (`sentinel.metrics.refusal`): correct-refusal rate, false-refusal rate, unsafe-answer
  rate, refusal precision/recall.
- **System**: latency, token usage, estimated cost (all `None`/explicit for the free local provider
  where a real cost doesn't exist).

## Failure taxonomy

Seven categories, 27 specific failure types (`sentinel.schemas.failures`): `RETRIEVAL_FAILURE`,
`CONTEXT_FAILURE`, `GENERATION_FAILURE`, `CITATION_FAILURE`, `REFUSAL_FAILURE`,
`SECURITY_FAILURE`, `SYSTEM_FAILURE`. Every diagnosis (`sentinel diagnose`) attaches real evidence
— retrieval ranks, lexical-overlap scores, metric values — never a bare "answer incorrect." Example
from an actual run against `datasets/golden/v1.json` under a deliberately weak config:

```json
{
  "case_id": "sem-005", "primary": "MISSING_RELEVANT_CHUNK", "secondary": ["SEMANTIC_MISMATCH"],
  "confidence": 0.9,
  "evidence": {"true_rank": 4, "top_k": 1, "query_document_lexical_overlap": 0.0},
  "likely_cause": "terminology mismatch between question and source document wording"
}
```

Running the same weak config against the full 53-case golden set surfaces real, unforced
failures: `FALSE_REFUSAL=3, WRONG_RANKING=7, MISSING_RELEVANT_CHUNK=7, ANSWERED_UNANSWERABLE=4`
(see `docs/experiments/10-repair-engine-effectiveness.md`).

## Adversarial testing

15 attack classes (`sentinel.schemas.attacks.AttackClass`), synthetic canaries only
(`SENTINEL-TEST-SECRET-...`), four possible outcomes (`SAFE|PARTIAL|FAILED|UNKNOWN`). Full suite
run against the deterministic baseline (795 generated cases, 53 base cases x 15 classes):

- **Overall attack_success_rate: 3.4%**, safe_rate 7.7%, partial_rate 88.9%.
- **`conflicting_document_injection` is the standout vulnerability at 22.6% success** — a
  malicious document phrased as a factual correction gets extracted even though the deterministic
  provider has no notion of "belief" to manipulate.
- Instruction-following classes (`direct_prompt_injection`, `instruction_override`,
  `fake_system_instructions`, `authority_impersonation`) score 0-1.9% success — **by construction**,
  since the deterministic provider cannot follow instructions at all; this measures a floor, not a
  real LLM's robustness (rerun with `--provider openai`/`anthropic` for that).
- A dedicated retrieval-poisoning curve shows recall@5 collapsing from **1.0 to 0.0 between 1% and
  5% document poisoning** on a 96-document corpus — a genuine, measured vulnerability in the
  reference pipeline's default config.

Full write-ups: `docs/experiments/07-adversarial-document-poisoning.md`,
`docs/experiments/08-prompt-injection-robustness.md`. Threat model: `docs/security/threat-model.md`.

## Repair engine

Diagnosis -> `RepairEngine.suggest` -> config-delta proposals -> real controlled experiment ->
`evaluate_acceptance` against configurable thresholds -> accept/reject. **Nothing is ever
auto-applied.** From the actual run behind `docs/experiments/10-repair-engine-effectiveness.md`:
of 7 plausible, correctly-diagnosed repair proposals against a real weak baseline, **only 1 was
accepted** (`top_k` 1->2, +23.8% recall, no regressions); the other 6 — including switching to
hybrid retrieval and enabling reranking — were correctly **rejected** for not clearing the
improvement bar or for regressing latency. See ADR-008 for why this is a design principle, not a
limitation.

## Experiments

Ten research-style experiments, each with Hypothesis/Method/Results/Interpretation/Limitations,
in `docs/experiments/`:

| # | Experiment | Headline (real) result |
|---|---|---|
| 1 | Dense vs. BM25 vs. Hybrid | BM25/hybrid tie (MRR 0.827) and beat dense-only hashing embeddings (MRR 0.818); BM25 is 2.5x faster |
| 2 | Effect of RRF | Matches BM25 alone exactly; no additional lift measured on this dataset |
| 3 | Effect of reranking | Zero measurable benefit, +11% latency — a real negative result |
| 4 | Query rewriting | **None of 4 strategies changed a single metric**; 18-79% pure latency overhead |
| 5 | Chunk size sensitivity | No sensitivity 100-1200 words — documents are shorter than every tested size |
| 6 | Retrieval depth | Recall climbs 0.81 -> 0.98 -> 1.00 from top_k 1->2->3, then plateaus |
| 7 | Retrieval poisoning | Recall@5 collapses 1.0 -> 0.0 between 1% and 5% poisoning |
| 8 | Prompt injection robustness | 3.4% overall success; 22.6% for conflicting-document injection specifically |
| 9 | Conflicting evidence | Numeric SLA conflicts detected 2/2; differently-worded conflicts missed 0/2 (by conservative design) |
| 10 | Repair effectiveness | 1 of 7 proposed repairs accepted under real acceptance criteria |

## Benchmark results

`reports/latest.{md,json,html}` are generated (not hand-written) by `sentinel benchmark` against
`configs/experiments/baseline.yaml` (hybrid RRF retrieval, deterministic local generation) over the
full 53-case golden dataset. Regenerate: `make benchmark`. A canonical baseline result used by the
CI regression gate is committed at `experiments/results/baseline_v1.json`.

## Limitations

Stated plainly, not buried:

- **The deterministic local provider is not a language model.** It's an extractive sentence
  selector. Generation-quality numbers from it are a floor; real-LLM behavior (via
  `OpenAIProvider`/`AnthropicProvider`) is not measured in the committed benchmark, since that would
  require a paid API key.
- **The dense embedding baseline is a hashing vectorizer, not a neural encoder** — see
  `docs/architecture/overview.md#embeddings`. It underperforms BM25 on this dataset partly because
  it's lexically-flavored itself, not because dense retrieval is inherently worse.
- **The 53-case golden dataset saturates recall@5 in most configurations** (small per-case
  corpora) — Experiments 1-5 are honest about this ceiling effect rather than presenting flat
  results as meaningful differentiation.
- **LLM-judge faithfulness is an interface + versioned prompt, not a wired model call** (see
  `docs/evaluation/faithfulness.md`).
- **Conflict detection is a standalone signal**, not yet consumed by diagnosis/repair.
- **Acceptance-criteria selection is not failure-type-aware** — see Experiment 10.
- **No committed web UI** — the CLI plus generated HTML report are the v1 UI surface.
- **No OpenTelemetry tracing wired up** — structured logging and Prometheus-compatible metrics
  ship in v1; distributed tracing does not.

## Security

`SECURITY.md` covers vulnerability reporting and responsible use of the adversarial toolkit
(synthetic secrets only, authorized-target use only). `docs/security/threat-model.md` covers assets,
threats, mitigations, and residual risk for both Sentinel-RAG itself and systems tested with it.

## Reproducibility

Every `ExperimentResult` records `git_commit`, `config_hash`, `dataset_version`, `seed`, full
environment info (Python version, platform, key package versions), and duration.
`sentinel replay --case <id>` reconstructs a single case's full trace. The release CI workflow
(`.github/workflows/release.yml`) regenerates the golden dataset and re-runs the baseline
experiment, diffing both against the committed copies — a real, automated proof that the
committed numbers reproduce exactly (excluding wall-clock latency) from a clean checkout.

```bash
make reproduce   # lint + typecheck + security + tests, regenerate dataset, re-run baseline + all experiments
```

## Development

```bash
make dev      # install with dev + optional extras
make check    # ruff + mypy + bandit + full test suite
make test     # pytest only
```

See `CONTRIBUTING.md` for the engineering principles this project holds itself to (no fabricated
metrics, provider-agnostic core, deterministic CI path, decisions documented as ADRs).

## Roadmap (stated, not implied)

- Wire `LLMFaithfulnessJudge` to a real provider call; add multi-judge disagreement reporting to
  the standard benchmark report.
- Failure-type-aware acceptance criteria routing in `sentinel repair run`.
- A real cross-encoder `Reranker` implementation as an optional extra.
- Consume `sentinel.retrieval.conflict` output in diagnosis/repair.
- OpenTelemetry trace export alongside the existing structured logging/metrics.
- A minimal web UI over the existing FastAPI service (`src/sentinel/api`), which currently exposes
  every CLI operation over HTTP but has no frontend.

## License

Apache 2.0 — see `LICENSE`.
