"""Mechanical answer-relevance proxy: token overlap between the generated
answer and the reference/acceptable answers. This is a LEXICAL proxy, not
semantic similarity — a correct paraphrase with little word overlap will
score low. Documented as a floor signal; a real deployment should pair
this with an LLM-judge or embedding-similarity score (extension point:
sentinel.evaluation.faithfulness.LLMFaithfulnessJudge follows the same
pattern and can be mirrored for relevance).
"""

from __future__ import annotations

from sentinel.retrieval.tokenize import tokenize


def lexical_answer_relevance(answer_text: str, references: list[str]) -> float | None:
    references = [r for r in references if r.strip()]
    if not references:
        return None
    answer_tokens = set(tokenize(answer_text))
    if not answer_tokens:
        return 0.0
    best = 0.0
    for ref in references:
        ref_tokens = set(tokenize(ref))
        if not ref_tokens:
            continue
        overlap = len(answer_tokens & ref_tokens) / len(answer_tokens | ref_tokens)
        best = max(best, overlap)
    return best
