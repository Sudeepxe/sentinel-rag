"""A from-scratch Okapi BM25 index.

Implemented directly (rather than depending on rank_bm25) so behavior is
fully understood, testable, and dependency-light. Standard Robertson/Sparck
Jones formulation with k1/b parameters.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from sentinel.retrieval.tokenize import tokenize
from sentinel.schemas.documents import Chunk


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks = chunks
        self._doc_tokens: list[list[str]] = [tokenize(c.text) for c in chunks]
        self._doc_lens = [len(toks) for toks in self._doc_tokens]
        self._avgdl = sum(self._doc_lens) / len(self._doc_lens) if self._doc_lens else 0.0
        self._df: dict[str, int] = defaultdict(int)
        self._term_freqs: list[Counter[str]] = []
        for toks in self._doc_tokens:
            tf = Counter(toks)
            self._term_freqs.append(tf)
            for term in tf:
                self._df[term] += 1
        n = len(chunks)
        self._idf: dict[str, float] = {
            term: math.log(1 + (n - df + 0.5) / (df + 0.5)) for term, df in self._df.items()
        }

    def score(self, query: str) -> list[float]:
        q_tokens = tokenize(query)
        scores = [0.0] * len(self.chunks)
        for i, tf in enumerate(self._term_freqs):
            dl = self._doc_lens[i]
            denom_norm = self.k1 * (1 - self.b + self.b * dl / self._avgdl) if self._avgdl else self.k1
            s = 0.0
            for term in q_tokens:
                if term not in tf:
                    continue
                idf = self._idf.get(term, 0.0)
                f = tf[term]
                s += idf * (f * (self.k1 + 1)) / (f + denom_norm)
            scores[i] = s
        return scores
