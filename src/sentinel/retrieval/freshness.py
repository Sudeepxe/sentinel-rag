"""Staleness/authority-aware re-scoring (spec section 18).

Policies:
- no-preference: scores unchanged.
- latest: boosts more recent documents.
- highest-authority: boosts higher-authority sources.
- latest-with-authority: combines both, authority weighted higher on ties.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sentinel.schemas.documents import Chunk

POLICIES = ("no-preference", "latest", "highest-authority", "latest-with-authority")


def _recency_weight(ts: datetime | None, now: datetime) -> float:
    if ts is None:
        return 0.5
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    age_days = max((now - ts).total_seconds() / 86400.0, 0.0)
    # Exponential decay, half-life ~ 365 days.
    return 0.5 ** (age_days / 365.0)


def apply_freshness_policy(
    chunks: list[Chunk], scores: list[float], policy: str, now: datetime | None = None
) -> list[float]:
    if policy not in POLICIES:
        raise ValueError(f"unknown freshness policy: {policy!r}")
    if policy == "no-preference":
        return scores

    now = now or datetime.now(UTC)
    adjusted = []
    for chunk, score in zip(chunks, scores, strict=True):
        recency = _recency_weight(chunk.timestamp, now)
        authority = chunk.authority
        if policy == "latest":
            factor = 0.5 + 0.5 * recency
        elif policy == "highest-authority":
            factor = 0.5 + 0.5 * authority
        else:  # latest-with-authority
            factor = 0.3 + 0.35 * recency + 0.35 * authority
        adjusted.append(score * factor)
    return adjusted
