from __future__ import annotations

from sentinel.generation.base import GenerationProvider
from sentinel.generation.deterministic import DeterministicLocalProvider

_REGISTRY: dict[str, type[GenerationProvider]] = {
    "deterministic_local": DeterministicLocalProvider,
}


def register_provider(name: str, cls: type[GenerationProvider]) -> None:
    _REGISTRY[name] = cls


def get_generation_provider(name: str) -> GenerationProvider:
    if name == "openai":
        from sentinel.generation.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if name == "anthropic":
        from sentinel.generation.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name not in _REGISTRY:
        raise ValueError(
            f"unknown generation provider {name!r}; available: {sorted(_REGISTRY) + ['openai', 'anthropic']}"
        )
    return _REGISTRY[name]()
