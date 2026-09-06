"""Citation inspection: does a cited chunk actually support the claim it is
attached to? (spec section 10)

`lexical_support_score` is the deterministic, mechanical proxy for
"supports" — token-overlap based, conservative by design. It is not a
substitute for an LLM/human judgment of entailment, and is explicitly
labeled `method="mechanical"` everywhere it surfaces in a report. A
stronger (and slower/paid) judgment is available via
sentinel.evaluation.faithfulness.LLMFaithfulnessJudge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sentinel.retrieval.tokenize import tokenize

SUPPORT_THRESHOLD = 0.28
_INLINE_CITATION_RE = re.compile(r"\[([\w:\-.]+)\]")

# Claim-unit splitting: a plain sentence boundary (.!?) splits claims,
# UNLESS it is immediately followed by a citation bracket — in that case
# the bracket belongs to the sentence before it, so the real split point
# is after the bracket instead. Without the negative lookahead, "Sentence.
# [chunk_id] Next sentence." mis-splits into "Sentence." (uncited) and
# "[chunk_id] Next sentence." (wrongly cited) — a one-position citation
# shift that was caught by tests/property citation round-trip tests.
_CLAIM_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?!\[)|(?<=\])\s+")


@dataclass
class Claim:
    index: int
    text: str
    inline_citation_ids: list[str] = field(default_factory=list)


def _claim_units(text: str) -> list[str]:
    return [u.strip() for u in _CLAIM_SPLIT_RE.split(text.strip()) if u.strip()]


def extract_claims(answer_text: str) -> list[Claim]:
    claims = []
    for idx, raw_unit in enumerate(_claim_units(answer_text)):
        cited = _INLINE_CITATION_RE.findall(raw_unit)
        clean_text = _INLINE_CITATION_RE.sub("", raw_unit).strip()
        if not clean_text:
            continue
        claims.append(Claim(index=idx, text=clean_text, inline_citation_ids=cited))
    return claims


def lexical_support_score(chunk_text: str, claim_text: str) -> float:
    chunk_tokens = set(tokenize(chunk_text))
    claim_tokens = set(tokenize(claim_text))
    if not claim_tokens:
        return 0.0
    # Overlap coefficient (relative to the smaller/claim set) rather than
    # Jaccard: a long chunk supporting a short precise claim should still
    # score highly if it contains all the claim's salient terms.
    return len(chunk_tokens & claim_tokens) / len(claim_tokens)


@dataclass
class CitationCheck:
    claim: Claim
    cited_chunk_ids: list[str]
    best_support_score: float
    supported: bool
    has_citation: bool


def check_citations(
    claims: list[Claim],
    global_citation_chunk_ids: list[str],
    chunks_by_id: dict[str, str],
    threshold: float = SUPPORT_THRESHOLD,
) -> list[CitationCheck]:
    """chunks_by_id: chunk_id -> chunk text (only chunks actually shown to the generator)."""
    results = []
    for claim in claims:
        cited_ids = claim.inline_citation_ids or global_citation_chunk_ids
        has_citation = bool(cited_ids)
        best_score = 0.0
        for cid in cited_ids:
            text = chunks_by_id.get(cid)
            if text is None:
                continue
            best_score = max(best_score, lexical_support_score(text, claim.text))
        results.append(
            CitationCheck(
                claim=claim,
                cited_chunk_ids=cited_ids,
                best_support_score=best_score,
                supported=has_citation and best_score >= threshold,
                has_citation=has_citation,
            )
        )
    return results


def citation_precision(checks: list[CitationCheck]) -> float | None:
    cited = [c for c in checks if c.has_citation]
    if not cited:
        return None
    return sum(1 for c in cited if c.supported) / len(cited)


def citation_recall(checks: list[CitationCheck]) -> float | None:
    if not checks:
        return None
    return sum(1 for c in checks if c.supported) / len(checks)


def unsupported_claims(checks: list[CitationCheck]) -> list[Claim]:
    return [c.claim for c in checks if not c.supported]
