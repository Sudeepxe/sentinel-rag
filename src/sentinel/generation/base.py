from __future__ import annotations

from abc import ABC, abstractmethod

from sentinel.schemas.experiments import GenerationConfig
from sentinel.schemas.generation import GenerationOutput
from sentinel.schemas.retrieval import RetrievalHit


class GenerationProvider(ABC):
    name: str
    is_deterministic_local: bool = False

    @abstractmethod
    def generate(
        self, query: str, hits: list[RetrievalHit], config: GenerationConfig
    ) -> GenerationOutput: ...


class ProviderError(RuntimeError):
    """Raised on provider-level failure (timeout, malformed output, rate limit)."""


class ProviderTimeoutError(ProviderError):
    pass


class ProviderMalformedResponseError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass
