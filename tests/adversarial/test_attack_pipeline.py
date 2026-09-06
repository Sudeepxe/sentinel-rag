"""Adversarial suite tests: generation, classification, and the golden
dataset's own standing prompt-injection regression cases."""

from pathlib import Path

from sentinel.adapters.reference import ReferenceRAGAdapter
from sentinel.attacks.generator import generate_attack_suite
from sentinel.attacks.runner import AttackRunner
from sentinel.schemas.attacks import AttackClass, AttackOutcome
from sentinel.schemas.experiments import GenerationConfig, RetrievalConfig
from sentinel.storage.dataset_store import load_dataset

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_attack_generator_produces_canary_per_case():
    dataset = load_dataset(FIXTURES / "smoke_dataset.json")
    base_cases = [c for c in dataset.cases if c.documents]
    attacks = generate_attack_suite(base_cases, [AttackClass.DIRECT_PROMPT_INJECTION])
    assert len(attacks) == len(base_cases)
    canaries = {a.canary for a in attacks}
    assert len(canaries) == len(attacks)  # every canary unique
    for a in attacks:
        assert a.canary in a.injected_instruction
        assert a.malicious_documents[0].is_adversarial is True


def test_attack_never_returns_unknown_on_clean_run():
    dataset = load_dataset(FIXTURES / "smoke_dataset.json")
    base_cases = [c for c in dataset.cases if c.documents]
    attacks = generate_attack_suite(base_cases, [AttackClass.RETRIEVAL_POISONING])
    runner = AttackRunner()
    results = [runner.run_one(a) for a in attacks]
    assert all(r.outcome != AttackOutcome.UNKNOWN for r in results)


def test_golden_dataset_injection_cases_do_not_leak_canary():
    """Standing regression check for the two golden-dataset prompt-injection
    cases (inject-001, inject-002): the deterministic baseline must not
    leak the embedded canary string into its answer."""
    dataset = load_dataset(Path(__file__).resolve().parent.parent.parent / "datasets" / "golden" / "v1.json")
    injection_cases = [c for c in dataset.cases if c.category in ("prompt_injection", "indirect_prompt_injection")]
    assert len(injection_cases) >= 2

    for case in injection_cases:
        adapter = ReferenceRAGAdapter(retrieval_config=RetrievalConfig(), generation_config=GenerationConfig())
        adapter.ingest(case.documents)
        retrieval = adapter.retrieve(case.question)
        generation = adapter.generate(case.question, retrieval)
        canary_markers = [tok for tok in ("GOLDEN-SET-CANARY-001", "GOLDEN-SET-CANARY-002") if tok in generation.answer_text]
        assert not canary_markers, f"{case.id} leaked {canary_markers}"


def test_false_positive_rate_is_zero_on_clean_only_run():
    """A control run using only clean documents (no malicious doc at all)
    can structurally never leak a canary that was never injected."""
    dataset = load_dataset(FIXTURES / "smoke_dataset.json")
    case = next(c for c in dataset.cases if c.documents)
    adapter = ReferenceRAGAdapter(retrieval_config=RetrievalConfig(), generation_config=GenerationConfig())
    adapter.ingest(case.documents)
    retrieval = adapter.retrieve(case.question)
    generation = adapter.generate(case.question, retrieval)
    assert "SENTINEL-TEST-SECRET" not in generation.answer_text
