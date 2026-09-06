"""Real OpenAI generation provider.

Requires `pip install sentinel-rag[providers]` and `OPENAI_API_KEY` in the
environment. Not used by default, not called in CI/tests (no network
access, no key). This is the plug-in point for evaluating an actual
frontier model rather than the deterministic local baseline.
"""

from __future__ import annotations

import os
import re
import time

from sentinel.generation.base import (
    GenerationProvider,
    ProviderMalformedResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from sentinel.generation.prompts import (
    ANSWER_SYSTEM_PROMPT,
    ANSWER_USER_TEMPLATE,
    build_evidence_block,
)
from sentinel.schemas.experiments import GenerationConfig
from sentinel.schemas.generation import Citation, GenerationOutput
from sentinel.schemas.retrieval import RetrievalHit

_CITATION_RE = re.compile(r"\[([\w:\-.]+)\]")

# Approximate public per-1K-token pricing, set explicitly per model so cost
# estimates are never silently wrong; unknown models report cost=None.
_PRICE_PER_1K_USD: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
}


class OpenAIProvider(GenerationProvider):
    name = "openai"
    is_deterministic_local = False

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. The OpenAI provider requires a real API key; use "
                "GenerationConfig(provider='deterministic_local') for offline/CI evaluation."
            )
        try:
            import openai  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "openai package not installed. Install with `pip install sentinel-rag[providers]`."
            ) from exc

    def generate(
        self, query: str, hits: list[RetrievalHit], config: GenerationConfig
    ) -> GenerationOutput:
        import openai

        client = openai.OpenAI(api_key=self.api_key)
        context_hits = hits[: config.max_context_chunks]
        evidence_block = build_evidence_block([(h.chunk.id, h.chunk.text) for h in context_hits])
        user_prompt = ANSWER_USER_TEMPLATE.format(question=query, evidence_block=evidence_block)

        start = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=config.model,
                temperature=config.temperature,
                messages=[
                    {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except openai.RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except openai.APIError as exc:
            raise ProviderMalformedResponseError(str(exc)) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        choice = response.choices[0] if response.choices else None
        if choice is None or choice.message.content is None:
            raise ProviderMalformedResponseError("OpenAI response had no message content")

        text = choice.message.content
        citations = [
            Citation(chunk_id=cid, claim_index=None) for cid in dict.fromkeys(_CITATION_RE.findall(text))
        ]
        refused = "don't have enough" in text.lower() or "cannot answer" in text.lower()

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else None
        completion_tokens = usage.completion_tokens if usage else None
        cost = None
        if usage and config.model in _PRICE_PER_1K_USD:
            in_price, out_price = _PRICE_PER_1K_USD[config.model]
            cost = (usage.prompt_tokens / 1000) * in_price + (usage.completion_tokens / 1000) * out_price

        return GenerationOutput(
            answer_text=text,
            refused=refused,
            citations=citations,
            provider=self.name,
            model=config.model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=cost,
            raw_prompt=user_prompt,
            is_deterministic_local=False,
        )
