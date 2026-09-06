"""Versioned evaluation dataset schema.

A DatasetCase is deliberately rich: it carries enough ground truth to
compute retrieval, citation, and refusal metrics mechanically, without
requiring an LLM judge for the base metrics.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from sentinel.schemas.documents import Document


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class DatasetCase(BaseModel):
    id: str
    question: str
    documents: list[Document] = Field(
        default_factory=list,
        description="Documents visible to retrieval for this case (a small local corpus slice).",
    )
    relevant_document_ids: list[str] = Field(default_factory=list)
    relevant_chunk_ids: list[str] = Field(
        default_factory=list,
        description="Populated after chunking if known ahead of time; otherwise left empty and "
        "resolved at evaluation time from relevant_document_ids.",
    )
    reference_answer: str | None = None
    acceptable_answers: list[str] = Field(default_factory=list)
    should_answer: bool = True
    expected_citations: list[str] = Field(default_factory=list)
    difficulty: Difficulty = Difficulty.MEDIUM
    tags: list[str] = Field(default_factory=list)
    attack_labels: list[str] = Field(default_factory=list)
    category: str = "uncategorized"
    notes: str = ""

    @model_validator(mode="after")
    def _validate_consistency(self) -> DatasetCase:
        if not self.question.strip():
            raise ValueError(f"case {self.id}: question must be non-empty")
        if not self.should_answer and self.reference_answer:
            raise ValueError(
                f"case {self.id}: should_answer=False cases must not carry a reference_answer"
            )
        if self.should_answer and not self.reference_answer and not self.acceptable_answers:
            raise ValueError(
                f"case {self.id}: answerable cases require reference_answer or acceptable_answers"
            )
        doc_ids = {d.id for d in self.documents}
        for rid in self.relevant_document_ids:
            if rid not in doc_ids:
                raise ValueError(
                    f"case {self.id}: relevant_document_ids references unknown document {rid!r}"
                )
        return self


class EvaluationDataset(BaseModel):
    name: str
    version: str
    description: str = ""
    cases: list[DatasetCase]

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> EvaluationDataset:
        ids = [c.id for c in self.cases]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate case ids in dataset {self.name}: {sorted(dupes)}")
        return self

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in self.cases:
            counts[case.category] = counts.get(case.category, 0) + 1
        return counts
