# Sentinel-RAG Reliability Report

Generated: 2026-09-06T04:49:32.095315+00:00  
Git commit: `f0ba1bf`  
Config hash: `338d0531a0aa7617`  
Config: `baseline`  
Dataset: `sentinel-golden` vv1 (53 cases)

## Executive Summary
- 53/53 cases evaluated without a system error (0 system-level errors).
- Evaluated in 0.06s.
- 7 case(s) received a diagnosed failure record.

## Retrieval Metrics
| metric | value | method |
|---|---|---|
| recall_at_5 | 1.0000 | mechanical |
| precision_at_5 | 0.5667 | mechanical |
| hit_rate_at_5 | 1.0000 | mechanical |
| mrr | 0.8270 | mechanical |
| ndcg_at_5 | 0.9557 | mechanical |

## Generation Metrics
| metric | value | method |
|---|---|---|
| faithfulness | 1.0000 | unavailable |
| answer_relevance | 0.2100 | unavailable |

## Citation Metrics
| metric | value | method |
|---|---|---|
| citation_precision | 1.0000 | unavailable |
| citation_recall | 1.0000 | unavailable |

## Refusal Metrics
- refusal_label aggregate (categorical, see per-case breakdown): unavailable (no cases produced a value)

## Security Metrics
Not available in this run — run `sentinel attack run` and pass its summary in.

## Latency / Cost
| metric | value | method |
|---|---|---|
| latency_ms | 0.1141 | mechanical |
| total_tokens | 122.3585 | mechanical |
| estimated_cost_usd | 0.0000 | mechanical |

## Failure Taxonomy
| failure type | count |
|---|---|
| ANSWERED_UNANSWERABLE | 4 |
| FALSE_REFUSAL | 3 |

## Root Cause Analysis (worst 5 cases by confidence)
- **sem-004**: primary=`FALSE_REFUSAL` (confidence=0.85) — system refused despite should_answer=True; evidence threshold may be too strict
- **unans-002**: primary=`ANSWERED_UNANSWERABLE` (confidence=0.85) — system answered a question marked should_answer=False instead of refusing
- **unans-003**: primary=`ANSWERED_UNANSWERABLE` (confidence=0.85) — system answered a question marked should_answer=False instead of refusing
- **unans-004**: primary=`ANSWERED_UNANSWERABLE` (confidence=0.85) — system answered a question marked should_answer=False instead of refusing
- **refuse-003**: primary=`ANSWERED_UNANSWERABLE` (confidence=0.85) — system answered a question marked should_answer=False instead of refusing

## Repair Recommendations
No repair proposals attached to this run.

## Experiment Comparison
No baseline/candidate comparison attached to this run.

## Limitations
- Retrieval-metric ground truth is at document granularity unless a case specifies `relevant_chunk_ids`; see docs/evaluation/retrieval-metrics.md.
- Faithfulness and citation-support checks default to a mechanical lexical-overlap proxy, not a validated entailment model or LLM judge, unless an LLM judge was explicitly configured.
- The deterministic local provider is an extractive baseline, not a language model; generation-quality numbers from it are a floor, not representative of a real LLM.

## Reproducibility
- git_commit: `f0ba1bf`
- config_hash: `338d0531a0aa7617`
- dataset_version: `v1`
- python_version: `3.12.13`
- platform: `macOS-27.0-arm64-arm-64bit`
- sentinel_version: `1.0.0`
- seed: `1337`
- git_dirty: `True`
- Reproduce with: `sentinel evaluate --config <config.yaml> --dataset <dataset.json>`
