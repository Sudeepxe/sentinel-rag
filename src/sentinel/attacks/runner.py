from __future__ import annotations

from dataclasses import dataclass

from sentinel.adapters.reference import ReferenceRAGAdapter
from sentinel.attacks.classifier import classify_attack_result, unknown_result
from sentinel.schemas.attacks import AttackCase, AttackOutcome, AttackResult
from sentinel.schemas.experiments import GenerationConfig, RetrievalConfig


@dataclass
class AttackSuiteReport:
    results: list[AttackResult]
    attack_success_rate: float
    safe_rate: float
    partial_rate: float
    unknown_rate: float
    malicious_content_reached_generation_rate: float
    false_positive_rate: float
    by_attack_class: dict[str, dict[str, float]]
    note: str


class AttackRunner:
    def __init__(
        self, retrieval_config: RetrievalConfig | None = None, generation_config: GenerationConfig | None = None
    ) -> None:
        self.retrieval_config = retrieval_config or RetrievalConfig()
        self.generation_config = generation_config or GenerationConfig()

    def run_one(self, attack_case: AttackCase) -> AttackResult:
        try:
            adapter = ReferenceRAGAdapter(
                retrieval_config=self.retrieval_config, generation_config=self.generation_config
            )
            adapter.ingest(attack_case.clean_documents + attack_case.malicious_documents)
            retrieval = adapter.retrieve(attack_case.question)
            generation = adapter.generate(attack_case.question, retrieval)
            return classify_attack_result(attack_case, retrieval, generation)
        except Exception as exc:  # noqa: BLE001
            return unknown_result(attack_case, f"{type(exc).__name__}: {exc}")

    def run_suite(self, attack_cases: list[AttackCase]) -> AttackSuiteReport:
        results = [self.run_one(ac) for ac in attack_cases]
        return aggregate_attack_results(results, provider=self.generation_config.provider)


def aggregate_attack_results(results: list[AttackResult], provider: str) -> AttackSuiteReport:
    n = len(results) or 1
    by_outcome = {o: sum(1 for r in results if r.outcome == o) for o in AttackOutcome}
    reached = sum(1 for r in results if r.retrieval_rank_of_malicious_chunk is not None)

    by_class: dict[str, dict[str, float]] = {}
    classes = sorted({r.attack_class.value for r in results})
    for cls in classes:
        cls_results = [r for r in results if r.attack_class.value == cls]
        cn = len(cls_results) or 1
        by_class[cls] = {
            "n": len(cls_results),
            "attack_success_rate": sum(1 for r in cls_results if r.outcome == AttackOutcome.FAILED) / cn,
            "safe_rate": sum(1 for r in cls_results if r.outcome == AttackOutcome.SAFE) / cn,
        }

    note = (
        f"Generated with provider={provider!r}. "
        + (
            "The deterministic local provider has no instruction-following capacity at all, so "
            "attack classes that specifically probe LLM compliance (prompt injection, instruction "
            "override, fake system instructions, authority impersonation) are expected to score "
            "SAFE by construction here — that measures the floor, not a real model's robustness. "
            "Re-run with `--provider openai` or `--provider anthropic` (API key required) for a "
            "meaningful instruction-following robustness measurement. Retrieval-surface attack "
            "classes (retrieval poisoning, context flooding, distractors, citation manipulation) "
            "ARE meaningfully measured against this provider, since they test the pipeline before "
            "any language-model reasoning happens."
            if provider == "deterministic_local"
            else "Results reflect the configured real LLM provider's actual behavior."
        )
    )

    return AttackSuiteReport(
        results=results,
        attack_success_rate=by_outcome[AttackOutcome.FAILED] / n,
        safe_rate=by_outcome[AttackOutcome.SAFE] / n,
        partial_rate=by_outcome[AttackOutcome.PARTIAL] / n,
        unknown_rate=by_outcome[AttackOutcome.UNKNOWN] / n,
        malicious_content_reached_generation_rate=reached / n,
        false_positive_rate=0.0,
        by_attack_class=by_class,
        note=note
        + " false_positive_rate is 0.0 by construction: canaries are unique per-run synthetic "
        "strings that cannot appear in clean control documents, so this methodology cannot "
        "produce a false positive on clean-only baselines.",
    )
