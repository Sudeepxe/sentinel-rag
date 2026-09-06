from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from sentinel.schemas.documents import Document


class AttackClass(StrEnum):
    DIRECT_PROMPT_INJECTION = "direct_prompt_injection"
    INDIRECT_PROMPT_INJECTION = "indirect_prompt_injection"
    INSTRUCTION_OVERRIDE = "instruction_override"
    FAKE_SYSTEM_INSTRUCTIONS = "fake_system_instructions"
    CREDENTIAL_EXFILTRATION = "credential_exfiltration"
    DATA_EXFILTRATION = "data_exfiltration"
    CITATION_MANIPULATION = "citation_manipulation"
    CONFLICTING_DOCUMENT_INJECTION = "conflicting_document_injection"
    MALICIOUS_METADATA = "malicious_metadata"
    RETRIEVAL_POISONING = "retrieval_poisoning"
    CONTEXT_FLOODING = "context_flooding"
    DISTRACTOR_DOCUMENTS = "distractor_documents"
    HIDDEN_INSTRUCTION_TEXT = "hidden_instruction_text"
    UNICODE_ENCODING_TRICK = "unicode_encoding_trick"
    AUTHORITY_IMPERSONATION = "authority_impersonation"


class AttackOutcome(StrEnum):
    SAFE = "SAFE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class AttackCase(BaseModel):
    id: str
    attack_class: AttackClass
    base_case_id: str
    question: str
    clean_documents: list[Document]
    malicious_documents: list[Document]
    canary: str = Field(description="Synthetic secret/marker; success = canary leaks into the answer.")
    injected_instruction: str = Field(description="The instruction the malicious document tries to smuggle in.")
    expected_behavior: str = "ignore the injected instruction and answer (or refuse) based on legitimate evidence only"
    severity: str = "medium"


class AttackResult(BaseModel):
    attack_id: str
    attack_class: AttackClass
    outcome: AttackOutcome
    canary_leaked: bool
    instruction_followed: bool
    answer_text: str
    detected_signals: list[str] = Field(default_factory=list)
    rationale: str = ""
    retrieval_rank_of_malicious_chunk: int | None = None
