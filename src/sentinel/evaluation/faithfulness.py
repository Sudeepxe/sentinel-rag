"""Faithfulness evaluation: are the claims in the answer supported by the
supplied evidence? (spec section 9)

Two layers, never conflated in reports:
1. Mechanical: sentinel.metrics.citation.lexical_support_score against ALL
   evidence shown to the generator (not just the cited chunk). Deterministic,
   free, always available — but a lexical proxy, not true entailment. It
   will under-count paraphrased support and over-count coincidental
   keyword overlap; treat it as a floor signal, not ground truth.
2. LLM-judge: an actual model scores (claim, evidence) -> supported/
   confidence/reasoning using the versioned prompt in
   sentinel.generation.prompts. Requires a real provider (OpenAI/Anthropic)
   and is OFF by default (mechanical-only) so CI never needs a paid key.
   When multiple judges run, disagreement is reported explicitly rather
   than silently averaged away.

Neither layer is presented as ground truth in the CLI/report output; the
`method` field on every MetricValue says which one produced the number.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sentinel.metrics.citation import Claim, lexical_support_score


@dataclass
class JudgeVerdict:
    claim_index: int
    supported: bool
    confidence: float
    reasoning: str
    judge_name: str


class FaithfulnessJudge(ABC):
    name: str
    is_llm_judge: bool

    @abstractmethod
    def judge(self, claim: Claim, evidence_texts: list[str]) -> JudgeVerdict: ...


class MechanicalFaithfulnessJudge(FaithfulnessJudge):
    """Deterministic lexical-overlap proxy. Always available."""

    name = "mechanical-lexical-v1"
    is_llm_judge = False

    def __init__(self, threshold: float = 0.28) -> None:
        self.threshold = threshold

    def judge(self, claim: Claim, evidence_texts: list[str]) -> JudgeVerdict:
        best = max((lexical_support_score(t, claim.text) for t in evidence_texts), default=0.0)
        return JudgeVerdict(
            claim_index=claim.index,
            supported=best >= self.threshold,
            confidence=min(best / max(self.threshold, 1e-6), 1.0),
            reasoning=f"lexical overlap score {best:.2f} vs threshold {self.threshold}",
            judge_name=self.name,
        )


class LLMFaithfulnessJudge(FaithfulnessJudge):
    """Real-LLM judge. Requires a configured provider; not used by default.

    Documented biases (see docs/evaluation/faithfulness.md):
    - Judge models are prompt-sensitive; JUDGE_PROMPT_VERSION pins the
      exact wording used to produce any historical score.
    - Judges tend toward leniency on fluent-sounding unsupported claims
      and can be stricter on correct claims phrased tersely.
    - Using the same model family for generation and judging inflates
      apparent faithfulness (self-preference bias); prefer a different
      model/vendor as judge than as generator where possible.
    """

    is_llm_judge = True

    def __init__(self, provider_name: str) -> None:
        from sentinel.generation.factory import get_generation_provider

        self._provider = get_generation_provider(provider_name)
        self.name = f"llm-judge-{provider_name}"

    def judge(self, claim: Claim, evidence_texts: list[str]) -> JudgeVerdict:
        raise NotImplementedError(
            "LLM-judge faithfulness requires a configured chat-completion call and a real "
            "API key; wire your provider's structured-output call here. Left as an explicit "
            "extension point rather than a fabricated implementation — see "
            "docs/evaluation/faithfulness.md for the exact contract expected."
        )


def compute_judge_disagreement(verdicts_by_judge: dict[str, list[JudgeVerdict]]) -> float | None:
    """Fraction of claims where judges disagree on `supported`. None if <2 judges."""
    judges = list(verdicts_by_judge.keys())
    if len(judges) < 2:
        return None
    n_claims = len(verdicts_by_judge[judges[0]])
    disagreements = 0
    for i in range(n_claims):
        verdicts = {verdicts_by_judge[j][i].supported for j in judges}
        if len(verdicts) > 1:
            disagreements += 1
    return disagreements / n_claims if n_claims else None
