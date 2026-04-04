"""
Shared canonical data models used across all ArbIt phases.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Market(BaseModel):
    """A single prediction market from any platform."""

    platform: str
    market_id: str
    question: str
    description: str | None = None
    outcomes: list[str]
    prices: dict[str, float]
    orderbook: dict[str, Any] | None = None
    fees: float = 0.0
    open_time: datetime | None = None
    close_time: datetime | None = None
    resolution_rules: str | None = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class CandidatePair(BaseModel):
    """A candidate pair of markets from Phase 2 similarity search."""

    candidate_id: str
    market_a: Market
    market_b: Market
    embedding_similarity: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateGroup(BaseModel):
    """A candidate group of markets (3+) from Phase 2 similarity search."""

    candidate_id: str
    markets: list[Market]
    embedding_similarities: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)
