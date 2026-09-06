"""Query rewriting strategies compared experimentally in
docs/experiments/04-query-rewriting.md — Sentinel does NOT assume rewriting
helps; the experiment measures it.

All strategies are deterministic and offline so they can run in CI. HyDE is
implemented as a lightweight local proxy (a templated "hypothetical
answer" built from question keywords, not an LLM-generated one) — this is
weaker than true HyDE but keeps the comparison provider-agnostic and free.
A real-LLM HyDE can be plugged in by passing a GenerationProvider.
"""

from __future__ import annotations

import re
from collections import Counter

from sentinel.retrieval.tokenize import tokenize

_DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "policy": ["policy", "guideline", "rule"],
    "retention": ["retention", "storage duration", "keep"],
    "refund": ["refund", "reimbursement", "money back"],
    "cancel": ["cancel", "terminate", "end"],
    "price": ["price", "cost", "fee"],
    "outage": ["outage", "downtime", "incident"],
    "latency": ["latency", "delay", "response time"],
}

_QUESTION_WORDS = {"what", "who", "when", "where", "why", "how", "which", "does", "is", "are", "do"}


def rewrite_none(question: str) -> list[str]:
    return [question]


def rewrite_expansion(question: str) -> list[str]:
    tokens = tokenize(question)
    extra_terms: list[str] = []
    for tok in tokens:
        for key, synonyms in _DOMAIN_SYNONYMS.items():
            if tok == key or tok.startswith(key):
                extra_terms.extend(s for s in synonyms if s != tok)
    expanded = question
    if extra_terms:
        expanded = question + " " + " ".join(dict.fromkeys(extra_terms))
    return [question, expanded] if expanded != question else [question]


def rewrite_hyde(question: str) -> list[str]:
    tokens = [t for t in tokenize(question) if t not in _QUESTION_WORDS]
    if not tokens:
        return [question]
    hypothetical = "The answer relates to " + " ".join(tokens) + "."
    return [question, hypothetical]


def rewrite_decompose(question: str) -> list[str]:
    parts = re.split(r"\band\b|;|\?\s*(?=[A-Z])", question)
    parts = [p.strip().rstrip("?").strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        return [question]
    return [question, *parts]


def rewrite_keyword(question: str) -> list[str]:
    tokens = tokenize(question)
    counts = Counter(tokens)
    top = [t for t, _ in counts.most_common(6)]
    if not top:
        return [question]
    return [question, " ".join(top)]


def rewrite_domain(question: str, glossary: dict[str, str] | None = None) -> list[str]:
    glossary = glossary or {}
    rewritten = question
    for casual, formal in glossary.items():
        rewritten = re.sub(rf"\b{re.escape(casual)}\b", formal, rewritten, flags=re.IGNORECASE)
    return [question, rewritten] if rewritten.lower() != question.lower() else [question]


STRATEGIES = {
    "none": rewrite_none,
    "expansion": rewrite_expansion,
    "hyde": rewrite_hyde,
    "decompose": rewrite_decompose,
    "keyword": rewrite_keyword,
}


def apply_strategy(strategy: str, question: str) -> list[str]:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown query rewrite strategy: {strategy!r}")
    return STRATEGIES[strategy](question)
