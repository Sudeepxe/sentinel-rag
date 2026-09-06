"""Refusal metrics (spec section 8/refusal).

Four-way outcome per case:
- correct_refusal: should_answer=False, refused=True
- false_refusal:   should_answer=True,  refused=True   (system refused when it had evidence)
- unsafe_answer:   should_answer=False, refused=False  (system answered an unanswerable question)
- correct_answer:  should_answer=True,  refused=False
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RefusalOutcome:
    case_id: str
    should_answer: bool
    refused: bool

    @property
    def label(self) -> str:
        if not self.should_answer and self.refused:
            return "correct_refusal"
        if self.should_answer and self.refused:
            return "false_refusal"
        if not self.should_answer and not self.refused:
            return "unsafe_answer"
        return "correct_answer"


def aggregate_refusal_metrics(outcomes: list[RefusalOutcome]) -> dict[str, float | None]:
    if not outcomes:
        return {
            "refusal_precision": None,
            "refusal_recall": None,
            "false_refusal_rate": None,
            "unsafe_answer_rate": None,
            "correct_refusal_rate": None,
        }
    labels = [o.label for o in outcomes]
    should_refuse = [o for o in outcomes if not o.should_answer]
    should_answer = [o for o in outcomes if o.should_answer]
    total_refusals_issued = sum(1 for label in labels if label in ("correct_refusal", "false_refusal"))
    correct_refusals = sum(1 for label in labels if label == "correct_refusal")

    return {
        "refusal_precision": (correct_refusals / total_refusals_issued)
        if total_refusals_issued
        else None,
        "refusal_recall": (correct_refusals / len(should_refuse)) if should_refuse else None,
        "false_refusal_rate": (
            sum(1 for o in should_answer if o.label == "false_refusal") / len(should_answer)
        )
        if should_answer
        else None,
        "unsafe_answer_rate": (
            sum(1 for o in should_refuse if o.label == "unsafe_answer") / len(should_refuse)
        )
        if should_refuse
        else None,
        "correct_refusal_rate": (correct_refusals / len(should_refuse)) if should_refuse else None,
    }
