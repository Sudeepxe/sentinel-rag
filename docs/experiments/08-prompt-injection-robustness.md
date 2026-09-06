# Experiment 8: Prompt Injection / Adversarial Robustness Suite

**Status:** run against all 795 generated attack cases (53 golden-set base cases x 15 attack
classes) with `provider=deterministic_local`. Regenerate with
`python scripts/run_all_experiments.py` or `sentinel attack generate` + `sentinel attack run`.

## Hypothesis

The deterministic extractive baseline, having no instruction-following capacity, will score SAFE
by construction against attack classes that rely on an LLM *choosing* to comply (prompt injection,
instruction override, fake system instructions, authority impersonation), while remaining
genuinely vulnerable to attack classes that operate purely at the retrieval/extraction layer
(conflicting-document injection, retrieval poisoning, citation manipulation).

## Method

`sentinel.attacks.generator.generate_attack_suite` built one `AttackCase` per (base case, attack
class) pair from every golden-set case that has documents, injecting one malicious document with a
unique synthetic canary (`SENTINEL-TEST-SECRET-...`) per case. `AttackRunner` ran each case through
the real `ReferenceRAGAdapter` (hybrid_rrf, top_k=5, deterministic_local generation) and classified
the outcome by whether the canary leaked into the final answer and/or the malicious chunk was
retrieved/cited.

## Results

Overall (n=795): **attack_success_rate = 3.40%**, safe_rate = 7.67%, partial_rate = 88.93%,
unknown_rate = 0%, malicious_content_reached_generation_rate = 92.33%.

| attack class | n | attack_success_rate | safe_rate |
|---|---|---|---|
| **conflicting_document_injection** | 53 | **22.6%** | 5.7% |
| unicode_encoding_trick | 53 | 7.5% | 9.4% |
| retrieval_poisoning | 53 | 7.5% | 7.5% |
| credential_exfiltration | 53 | 5.7% | 7.5% |
| indirect_prompt_injection | 53 | 3.8% | 7.5% |
| authority_impersonation | 53 | 1.9% | 7.5% |
| direct_prompt_injection | 53 | 1.9% | 9.4% |
| citation_manipulation | 53 | 0.0% | 5.7% |
| context_flooding | 53 | 0.0% | 7.5% |
| data_exfiltration | 53 | 0.0% | 7.5% |
| distractor_documents | 53 | 0.0% | 7.5% |
| fake_system_instructions | 53 | 0.0% | 7.5% |
| hidden_instruction_text | 53 | 0.0% | 9.4% |
| instruction_override | 53 | 0.0% | 5.7% |
| malicious_metadata | 53 | 0.0% | 9.4% |

## Interpretation

The hypothesis is **confirmed for most instruction-following classes but with one clear
exception**: `direct_prompt_injection`, `instruction_override`, `fake_system_instructions`, and
`authority_impersonation` all show near-zero (0-1.9%) attack success, consistent with the
deterministic baseline's structural inability to "follow" an instruction — it only extracts
query-relevant sentences. **`conflicting_document_injection` is the clear outlier at 22.6% attack
success** — far above every other class. Mechanically, this is the same phenomenon measured in
Experiment 7: a malicious document phrased as a factual correction ("the correct value is
`<canary>`, not what other documents claim") scores well on lexical overlap with the question
*and* looks like exactly the kind of short, direct factual sentence the extractive selector
prefers — it doesn't need the model to "believe" it, just to extract it. `unicode_encoding_trick`
and `retrieval_poisoning` also show non-trivial success (7.5% each) for the same underlying reason.
`safe_rate` is low across the board (5.7-9.4%) not because attacks are especially effective, but
because with only ~3 documents per case and top_k=5, the single injected malicious document is
almost always retrieved into context regardless of attack class (`malicious_content_reached_
generation_rate = 92.3%`) — see the note below on what SAFE actually measures here.

**`malicious_content_reached_generation_rate = 92.3%`** is a load-bearing number: it means the
retrieval layer essentially never filters out injected content at this corpus scale, so almost all
of the "safety" observed here comes from the generation layer's (structural, not learned)
disinterest in instructions — not from retrieval-side defense. This is a materially different
security posture than a system with retrieval-side anomaly detection or a real LLM with RLHF-based
injection resistance, and should not be read as "Sentinel-RAG's reference pipeline is safe."

## Limitations

- **This suite measures the deterministic local provider only.** Per the hypothesis, most
  instruction-following attack classes are expected (and confirmed) to be near-zero here *because
  the provider cannot follow instructions at all*, not because any defense was applied. Re-running
  with `sentinel attack run --config ... --provider openai` (API key required) against a real LLM
  is necessary to measure actual prompt-injection robustness, and would very plausibly show much
  higher success rates on the instruction-following classes — that is the whole point of shipping
  this suite as provider-agnostic infrastructure rather than a one-off number.
- `false_positive_rate = 0.0` is reported by construction (canaries are unique per-run synthetic
  strings that cannot appear in any clean control document), not as an empirically validated
  property of a defense mechanism — see `sentinel.attacks.runner.aggregate_attack_results`.
- Attack cases here inject exactly one malicious document per case; a multi-document coordinated
  attack was not tested.
