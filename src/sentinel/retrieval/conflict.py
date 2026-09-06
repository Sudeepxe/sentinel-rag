"""Conflicting-evidence detection (spec section 17).

Deterministic heuristic: within the retrieved chunk set, look for chunks
whose source/document differ but whose text shares a subject (high token
overlap on non-numeric tokens) while disagreeing on a number, date, or
polarity term. This is intentionally conservative (favors precision) since
false positives would make Sentinel over-flag benign redundant evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sentinel.retrieval.tokenize import tokenize
from sentinel.schemas.documents import Chunk

_NUMERIC_RE = re.compile(r"\b\d{1,4}(?:[.,]\d+)?\b")
_POLARITY_TERMS = {"yes", "no", "allowed", "not", "prohibited", "permitted", "denied", "approved"}


@dataclass
class ConflictSignal:
    chunk_id_a: str
    chunk_id_b: str
    shared_subject_overlap: float
    differing_values: list[str]


def detect_conflicts(chunks: list[Chunk], subject_overlap_threshold: float = 0.5) -> list[ConflictSignal]:
    signals: list[ConflictSignal] = []
    for i in range(len(chunks)):
        for j in range(i + 1, len(chunks)):
            a, b = chunks[i], chunks[j]
            if a.document_id == b.document_id:
                continue
            toks_a = set(tokenize(a.text))
            toks_b = set(tokenize(b.text))
            if not toks_a or not toks_b:
                continue
            overlap = len(toks_a & toks_b) / len(toks_a | toks_b)
            if overlap < subject_overlap_threshold:
                continue
            nums_a = set(_NUMERIC_RE.findall(a.text))
            nums_b = set(_NUMERIC_RE.findall(b.text))
            differing = list((nums_a - nums_b) | (nums_b - nums_a))
            pol_a = toks_a & _POLARITY_TERMS
            pol_b = toks_b & _POLARITY_TERMS
            if pol_a and pol_b and pol_a != pol_b:
                differing.append(f"polarity:{sorted(pol_a)}!={sorted(pol_b)}")
            if differing:
                signals.append(
                    ConflictSignal(
                        chunk_id_a=a.id,
                        chunk_id_b=b.id,
                        shared_subject_overlap=overlap,
                        differing_values=differing,
                    )
                )
    return signals
