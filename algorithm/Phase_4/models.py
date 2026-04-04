"""Phase 4 data models: MatchedPair, ArbitrageSignal, and supporting types."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Platform(str, Enum):
    POLYMARKET = "polymarket"
    KALSHI = "kalshi"
    MANIFOLD = "manifold"


class Direction(str, Enum):
    BUY_B_SELL_A = "buy_b_sell_a"  # B is cheap: buy YES on B, sell (buy NO) on A
    BUY_A_SELL_B = "buy_a_sell_b"  # A is cheap: buy YES on A, sell (buy NO) on B


class MarketInfo(BaseModel):
    """Minimal market pricing info needed by Phase 4."""

    platform: Platform
    market_id: str
    yes_price: float
    no_price: float
    volume_24h: float = 0.0
    close_date: datetime | None = None


class MatchedPair(BaseModel):
    """A Phase 3 ACCEPT'd candidate pair, ready for Phase 4 scoring."""

    pair_id: str
    market_a: MarketInfo
    market_b: MarketInfo
    similarity_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class PricePoint(BaseModel):
    """A single historical price snapshot stored in MongoDB."""

    platform: str
    market_id: str
    yes_price: float
    timestamp: datetime


class ArbitrageSignal(BaseModel):
    """Output of Phase 4 for a single matched pair."""

    pair_id: str
    market_a_id: str
    market_b_id: str
    platform_a: Platform
    platform_b: Platform
    price_a: float
    price_b: float
    raw_spread: float
    direction: Direction
    regression_convergence_prob: float
    expected_profit: float
    kelly_fraction: float
    recommended_size_usd: float
    confidence: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
