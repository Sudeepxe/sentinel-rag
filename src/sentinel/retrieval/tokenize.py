"""Minimal deterministic tokenizer shared by BM25 and lexical metrics.

Intentionally dependency-free (no nltk/spacy download) so the deterministic
path works fully offline.
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    ["a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "of", "to", "in", "on", "for", "with", "as", "at", "by", "from", "this", "that", "these", "those", "it", "its", "it's", "and", "or", "but", "if", "then", "than", "so", "not", "no", "nor", "do", "does", "did", "doing", "have", "has", "had", "having", "will", "would", "shall", "should", "can", "could", "may", "might", "must", "about", "into", "over", "under", "again", "further", "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "only", "own", "same"]
)


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    if remove_stopwords:
        tokens = [t for t in tokens if t not in _STOPWORDS]
    return tokens


def query_coverage(query_tokens: set[str], text: str) -> float:
    """Fraction of query_tokens present in text. Asymmetric by design: a
    short query against a long, mostly-irrelevant chunk should still score
    highly if the chunk happens to contain the query's key terms —
    symmetric Jaccard punishes this via a large union, which produced
    real false refusals in practice (see chunking.py docstring)."""
    if not query_tokens:
        return 0.0
    text_tokens = set(tokenize(text))
    return len(query_tokens & text_tokens) / len(query_tokens)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]
