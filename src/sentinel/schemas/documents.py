"""Document and chunk schemas.

Documents are the unit of ingestion; chunks are the unit of retrieval.
Both carry optional metadata used by staleness/authority-aware retrieval
policies (see sentinel.retrieval.freshness).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str
    title: str = ""
    text: str
    source: str = "unknown"
    authority: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relative trust/authority of the source, 0 (untrusted) to 1 (canonical).",
    )
    timestamp: datetime | None = Field(
        default=None, description="Document publication/last-updated time, if known."
    )
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    is_adversarial: bool = Field(
        default=False,
        description="True if this document was injected as an adversarial/poisoning test fixture.",
    )


class Chunk(BaseModel):
    id: str
    document_id: str
    text: str
    position: int = 0
    document_title: str = ""
    source: str = "unknown"
    authority: float = 0.5
    timestamp: datetime | None = None
    is_adversarial: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)
