from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str
    claim_index: int | None = Field(
        default=None, description="Index of the claim/sentence in the answer this citation supports."
    )


class GenerationOutput(BaseModel):
    answer_text: str
    refused: bool = False
    citations: list[Citation] = Field(default_factory=list)
    provider: str
    model: str
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_usd: float | None = None
    raw_prompt: str | None = None
    is_deterministic_local: bool = Field(
        default=False,
        description="True when produced by the deterministic local provider rather than a "
        "real frontier LLM. Reports must surface this distinction.",
    )
