"""Phase 5 data models: TradeAction and ValidatedOpportunity."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from algorithm.Phase_4.models import ArbitrageSignal, Platform


class TradeAction(BaseModel):
    """A concrete, executable trade action."""

    platform: Platform
    market_id: str
    side: str  # "yes" or "no"
    amount_usd: float
    limit_price: float


class ValidatedOpportunity(BaseModel):
    """Output of Phase 5: a signal that has passed all live validation checks."""

    signal: ArbitrageSignal
    live_price_a: float
    live_price_b: float
    live_spread: float
    spread_still_exists: bool
    liquidity_ok: bool
    price_correlation: float
    correlation_ok: bool
    executable: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    actions: list[TradeAction] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=datetime.utcnow)
