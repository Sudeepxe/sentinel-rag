"""Deterministic local generation provider.

This is an extractive answerer: it selects the sentences from retrieved
evidence with the highest lexical overlap to the query and stitches them
into an answer with per-sentence citations. It requires no API key, no
network access, and no model weights, so it is safe to run in CI and as
the default for the golden benchmark.

Honesty note (README/docs repeat this): this is NOT a language model. It
cannot paraphrase, synthesize across chunks, or be "convinced" by
instructions embedded in evidence — it has no instruction-following
capacity at all. That makes it a useful floor/baseline for retrieval and
citation-mechanics evaluation, and it is structurally immune to
prompt-injection attacks that rely on an LLM *deciding* to comply. It is
NOT a substitute for evaluating real frontier-model behavior — attack
classes that specifically probe instruction-following (prompt injection,
instruction override, fake system instructions, authority impersonation)
are reported as "safe by construction" against this provider, with an
explicit note to re-run against a real provider (OpenAI/Anthropic) for a
meaningful instruction-following robustness measurement.
"""

from __future__ import annotations

import time

from sentinel.generation.base import GenerationProvider
from sentinel.retrieval.tokenize import query_coverage, sentences, tokenize
from sentinel.schemas.experiments import GenerationConfig
from sentinel.schemas.generation import Citation, GenerationOutput
from sentinel.schemas.retrieval import RetrievalHit

_REFUSAL_TEXT = (
    "I don't have enough evidence in the retrieved context to answer this question confidently."
)


def _sentence_overlap(query_tokens: set[str], sentence: str) -> float:
    s_tokens = set(tokenize(sentence))
    if not query_tokens or not s_tokens:
        return 0.0
    return len(query_tokens & s_tokens) / len(query_tokens | s_tokens)


class DeterministicLocalProvider(GenerationProvider):
    name = "deterministic_local"
    is_deterministic_local = True

    def __init__(self, max_sentences: int = 3) -> None:
        self.max_sentences = max_sentences

    def generate(
        self, query: str, hits: list[RetrievalHit], config: GenerationConfig
    ) -> GenerationOutput:
        start = time.perf_counter()
        model = "sentinel-deterministic-v1"

        context_hits = hits[: config.max_context_chunks]
        if not context_hits:
            return self._refuse(start, model, prompt_tokens=len(tokenize(query, remove_stopwords=False)))

        chunks = [h.chunk for h in context_hits]
        query_tokens = set(tokenize(query))
        overlap_scores = [query_coverage(query_tokens, c.text) for c in chunks]
        evidence_score = max(overlap_scores) if overlap_scores else 0.0

        if evidence_score < config.refuse_below_evidence_score:
            prompt_tokens = sum(len(tokenize(c.text, remove_stopwords=False)) for c in chunks)
            return self._refuse(start, model, prompt_tokens=prompt_tokens)

        candidates: list[tuple[float, int, int, str, str]] = []  # score, rank, sent_idx, chunk_id, sentence
        for rank, hit in enumerate(context_hits):
            for sent_idx, sent in enumerate(sentences(hit.chunk.text)):
                score = _sentence_overlap(query_tokens, sent)
                candidates.append((score, rank, sent_idx, hit.chunk.id, sent))

        candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
        selected = [c for c in candidates if c[0] > 0][: self.max_sentences]
        if not selected:
            top_chunk = chunks[0]
            top_sentences = sentences(top_chunk.text)
            fallback_sentence = top_sentences[0] if top_sentences else top_chunk.text
            selected = [(evidence_score, 0, 0, top_chunk.id, fallback_sentence)]

        answer_parts = []
        citations = []
        for claim_idx, (_, _, _, chunk_id, sent) in enumerate(selected):
            answer_parts.append(f"{sent} [{chunk_id}]")
            citations.append(Citation(chunk_id=chunk_id, claim_index=claim_idx))

        answer_text = " ".join(answer_parts)
        prompt_tokens = sum(len(tokenize(c.text, remove_stopwords=False)) for c in chunks)
        completion_tokens = len(tokenize(answer_text, remove_stopwords=False))
        latency_ms = (time.perf_counter() - start) * 1000

        return GenerationOutput(
            answer_text=answer_text,
            refused=False,
            citations=citations,
            provider=self.name,
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=0.0,
            is_deterministic_local=True,
        )

    def _refuse(self, start: float, model: str, prompt_tokens: int) -> GenerationOutput:
        latency_ms = (time.perf_counter() - start) * 1000
        return GenerationOutput(
            answer_text=_REFUSAL_TEXT,
            refused=True,
            citations=[],
            provider=self.name,
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=len(tokenize(_REFUSAL_TEXT, remove_stopwords=False)),
            estimated_cost_usd=0.0,
            is_deterministic_local=True,
        )
