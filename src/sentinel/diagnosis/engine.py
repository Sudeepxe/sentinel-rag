"""DiagnosisEngine: runs all diagnosis rules for a case, picks a primary
failure by severity/confidence ordering, and attaches the rest as
secondary. Never emits a bare "answer incorrect" — every FailureRecord
carries the measured evidence that produced it (spec section 12).
"""

from __future__ import annotations

from sentinel.diagnosis.rules import (
    diagnose_citations,
    diagnose_generation,
    diagnose_refusal,
    diagnose_retrieval,
)
from sentinel.schemas.dataset import DatasetCase
from sentinel.schemas.evaluation import CaseEvaluation
from sentinel.schemas.failures import FailureRecord


class DiagnosisEngine:
    def diagnose(
        self, case: DatasetCase, evaluation: CaseEvaluation, full_ranking: list[str] | None = None
    ) -> list[FailureRecord]:
        # Retrieval failures are checked first: if retrieval missed the
        # evidence, downstream citation/generation failures are usually
        # consequences, not independent root causes.
        records: list[FailureRecord] = []
        for record in (
            diagnose_retrieval(case, evaluation, full_ranking),
            diagnose_refusal(case, evaluation),
            diagnose_citations(case, evaluation),
            diagnose_generation(case, evaluation),
        ):
            if record is not None:
                records.append(record)

        if len(records) > 1:
            primary = max(records, key=lambda r: r.confidence)
            others = [r for r in records if r is not primary]
            primary.secondary.extend(o.primary for o in others if o.primary not in primary.secondary)
            for other in others:
                primary.evidence[f"also_detected:{other.primary.value}"] = other.evidence
            return [primary]
        return records
