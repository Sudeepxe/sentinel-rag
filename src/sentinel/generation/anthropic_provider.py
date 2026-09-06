"""Real Anthropic generation provider.

Requires `pip install sentinel-rag[providers]` and `ANTHROPIC_API_KEY` in
the environment. Not used by default, not called in CI/tests.
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

_PRICE_PER_1K_USD: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (0.001, 0.005),
}


class AnthropicProvider(GenerationProvider):
    name = "anthropic"
    is_deterministic_local = False

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. The Anthropic provider requires a real API key; use "
                "GenerationConfig(provider='deterministic_local') for offline/CI evaluation."
            )
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "anthropic package not installed. Install with `pip install sentinel-rag[providers]`."
            ) from exc

    def generate(
        self, query: str, hits: list[RetrievalHit], config: GenerationConfig
    ) -> GenerationOutput:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        context_hits = hits[: config.max_context_chunks]
        evidence_block = build_evidence_block([(h.chunk.id, h.chunk.text) for h in context_hits])
        user_prompt = ANSWER_USER_TEMPLATE.format(question=query, evidence_block=evidence_block)

        start = time.perf_counter()
        try:
            response = client.messages.create(
                model=config.model,
                max_tokens=1024,
                temperature=config.temperature,
                system=ANSWER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.RateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except anthropic.APIError as exc:
            raise ProviderMalformedResponseError(str(exc)) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        if not text_blocks:
            raise ProviderMalformedResponseError("Anthropic response had no text content")
        text = "\n".join(text_blocks)

        citations = [
            Citation(chunk_id=cid, claim_index=None) for cid in dict.fromkeys(_CITATION_RE.findall(text))
        ]
        refused = "don't have enough" in text.lower() or "cannot answer" in text.lower()

        prompt_tokens = response.usage.input_tokens if response.usage else None
        completion_tokens = response.usage.output_tokens if response.usage else None
        cost = None
        if response.usage is not None and config.model in _PRICE_PER_1K_USD:
            in_price, out_price = _PRICE_PER_1K_USD[config.model]
            usage = response.usage
            cost = (usage.input_tokens / 1000) * in_price + (usage.output_tokens / 1000) * out_price

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
