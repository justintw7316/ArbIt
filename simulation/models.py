"""
Core data models for the ArbIt simulation / backtesting environment.

All types are Pydantic v2 BaseModels with strong typing.
This module is the single source of truth for shared types across all
simulation sub-modules.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    MARKET_CREATED = "market_created"
    MARKET_UPDATED = "market_updated"
    ORDERBOOK_SNAPSHOT = "orderbook_snapshot"
    TRADE_PRINT = "trade_print"
    MARKET_RESOLVED = "market_resolved"


class OrderSide(str, Enum):
    BUY = "buy"    # take the YES side / buy shares
    SELL = "sell"  # take the NO side / sell shares


class FillStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BasketStatus(str, Enum):
    PENDING = "pending"   # awaiting leg fills
    PARTIAL = "partial"   # some legs filled, others pending
    OPEN = "open"         # all legs filled, awaiting settlement
    CLOSED = "closed"     # fully settled
    FAILED = "failed"     # could not fill all legs; incomplete


class RealismMode(str, Enum):
    OPTIMISTIC = "optimistic"    # no slippage, min fees, instant fill
    REALISTIC = "realistic"      # model slippage, standard fees, modest latency
    PESSIMISTIC = "pessimistic"  # high slippage, max fees, conservative fills


class MarketStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Market data models
# ---------------------------------------------------------------------------


class OrderbookLevel(BaseModel):
    """A single price level in the orderbook."""

    price: float  # 0–1 probability price
    size: float   # available shares at this price


class MarketSnapshot(BaseModel):
    """Fully normalized market state at a point in time."""

    platform: str
    market_id: str
    question: str
    description: str | None = None
    outcomes: list[str]

    # Price layers
    best_bid: dict[str, float] = Field(default_factory=dict)   # outcome -> best bid
    best_ask: dict[str, float] = Field(default_factory=dict)   # outcome -> best ask
    last_traded: dict[str, float] = Field(default_factory=dict)

    # Orderbook depth (may be empty if not available)
    bids: dict[str, list[OrderbookLevel]] = Field(default_factory=dict)
    asks: dict[str, list[OrderbookLevel]] = Field(default_factory=dict)

    fees: float = 0.0
    status: MarketStatus = MarketStatus.ACTIVE
    close_time: datetime | None = None
    snapshot_time: datetime = Field(default_factory=datetime.utcnow)

    def mid_price(self, outcome: str) -> float | None:
        """Return mid-price for an outcome, or None if no quotes."""
        bid = self.best_bid.get(outcome)
        ask = self.best_ask.get(outcome)
        if bid is not None and ask is not None:
            return (bid + ask) / 2
        return self.last_traded.get(outcome)

    def visible_ask_size(self, outcome: str) -> float:
        """Total visible ask-side liquidity for an outcome."""
        levels = self.asks.get(outcome, [])
        return sum(lv.size for lv in levels)

    def visible_bid_size(self, outcome: str) -> float:
        """Total visible bid-side liquidity for an outcome."""
        levels = self.bids.get(outcome, [])
        return sum(lv.size for lv in levels)


# ---------------------------------------------------------------------------
# Historical replay events
# ---------------------------------------------------------------------------


class HistoricalReplayEvent(BaseModel):
    """A single time-stamped event from the historical record."""

    event_id: str
    event_type: EventType
    platform: str
    market_id: str
    timestamp: datetime
    data: dict[str, Any] = Field(default_factory=dict)

    # Parsed snapshot — populated by adapters for MARKET_UPDATED / ORDERBOOK_SNAPSHOT
    snapshot: MarketSnapshot | None = None

    model_config = {"frozen": False}


# ---------------------------------------------------------------------------
# Environment state models
# ---------------------------------------------------------------------------


class MarketState(BaseModel):
    """Current visible state of a single market as seen by the simulation."""

    market_id: str
    platform: str
    latest_snapshot: MarketSnapshot | None = None
    last_update_time: datetime | None = None
    status: MarketStatus = MarketStatus.ACTIVE
    resolution_outcome: str | None = None
    resolution_value: float | None = None  # 1.0 if outcome won, 0.0 if lost
    resolution_time: datetime | None = None


class EnvironmentState(BaseModel):
    """Complete state of the simulation environment at a point in time."""

    current_time: datetime
    market_states: dict[str, MarketState] = Field(default_factory=dict)
    event_count: int = 0
    step_count: int = 0


# ---------------------------------------------------------------------------
# Trade and position models
# ---------------------------------------------------------------------------


class BasketLeg(BaseModel):
    """A single leg of a multi-leg arbitrage basket."""

    leg_id: str
    platform: str
    market_id: str
    outcome: str
    side: OrderSide
    requested_size: float
    requested_price: float | None = None  # limit price hint

    # Filled state
    fill_price: float | None = None
    filled_size: float = 0.0
    fees_paid: float = 0.0
    fill_time: datetime | None = None
    fill_status: FillStatus = FillStatus.PENDING
    rejection_reason: str | None = None


class ArbBasket(BaseModel):
    """A multi-leg arbitrage basket from entry to settlement."""

    basket_id: str
    legs: list[BasketLeg]
    status: BasketStatus = BasketStatus.PENDING
    arb_type: str = "binary_pair"  # e.g. "binary_pair", "complement_basket"

    created_time: datetime
    open_time: datetime | None = None    # when all legs filled
    close_time: datetime | None = None  # when settled

    locked_capital: float = 0.0
    expected_profit: float = 0.0
    realized_pnl: float | None = None
    total_fees: float = 0.0
    total_slippage_cost: float = 0.0

    notes: str = ""

    @property
    def is_complete(self) -> bool:
        return all(l.fill_status == FillStatus.FILLED for l in self.legs)

    @property
    def has_partial_fills(self) -> bool:
        return any(l.fill_status == FillStatus.PARTIAL for l in self.legs)

    @property
    def leg_count(self) -> int:
        return len(self.legs)


class Position(BaseModel):
    """A single open position in a market outcome."""

    position_id: str
    platform: str
    market_id: str
    outcome: str
    side: OrderSide
    size: float
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    fees_paid: float = 0.0
    basket_id: str | None = None

    @property
    def unrealized_pnl(self) -> float:
        if self.side == OrderSide.BUY:
            return (self.current_price - self.entry_price) * self.size
        return (self.entry_price - self.current_price) * self.size


class PortfolioState(BaseModel):
    """Complete snapshot of the portfolio at a point in time."""

    cash: float
    locked_capital: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_fees_paid: float
    open_baskets: list[ArbBasket] = Field(default_factory=list)
    closed_baskets: list[ArbBasket] = Field(default_factory=list)
    positions: list[Position] = Field(default_factory=list)

    @property
    def open_basket_count(self) -> int:
        return len(self.open_baskets)


# ---------------------------------------------------------------------------
# Trade actions
# ---------------------------------------------------------------------------


class TradeAction(BaseModel):
    """A strategy-submitted request to enter an arbitrage basket."""

    action_id: str
    basket_id: str
    legs: list[BasketLeg]
    requested_time: datetime
    min_profit_threshold: float = 0.0
    max_size: float = float("inf")
    notes: str = ""


# ---------------------------------------------------------------------------
# Execution results
# ---------------------------------------------------------------------------


class FillResult(BaseModel):
    """The outcome of attempting to fill a TradeAction."""

    action_id: str
    basket_id: str
    legs: list[BasketLeg]
    fill_status: FillStatus
    total_fees: float = 0.0
    total_slippage_cost: float = 0.0
    locked_capital: float = 0.0
    expected_profit: float = 0.0
    fill_time: datetime
    rejection_reason: str | None = None


class SettlementResult(BaseModel):
    """Payout from a single leg when its market resolves."""

    basket_id: str
    leg_id: str
    platform: str
    market_id: str
    outcome: str
    resolution_outcome: str
    payout_per_share: float   # 1.0 if outcome won, 0.0 if lost
    shares_held: float
    gross_payout: float
    fees_deducted: float = 0.0
    net_payout: float
    settlement_time: datetime


# ---------------------------------------------------------------------------
# Observation (what the strategy sees)
# ---------------------------------------------------------------------------


class Observation(BaseModel):
    """The information exposed to the strategy at each timestep.

    Never contains future data — all fields reflect state at sim_time.
    """

    sim_time: datetime
    visible_markets: dict[str, MarketSnapshot] = Field(default_factory=dict)
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    portfolio: PortfolioState
    recent_fills: list[FillResult] = Field(default_factory=list)
    recent_settlements: list[SettlementResult] = Field(default_factory=list)

    @property
    def active_market_count(self) -> int:
        return sum(
            1 for s in self.visible_markets.values()
            if s.status == MarketStatus.ACTIVE
        )


# ---------------------------------------------------------------------------
# Analytics models
# ---------------------------------------------------------------------------


class BacktestMetrics(BaseModel):
    """Summary metrics for a completed backtest run."""

    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_fees_paid: float = 0.0
    total_slippage_cost: float = 0.0

    # Equity curve: list of (iso_timestamp, equity_value)
    equity_curve: list[tuple[str, float]] = Field(default_factory=list)

    opportunities_detected: int = 0
    trades_attempted: int = 0
    trades_filled: int = 0
    partial_fills: int = 0
    fill_rate: float = 0.0

    avg_profit_per_trade: float = 0.0
    max_locked_capital: float = 0.0
    avg_holding_period_hours: float = 0.0
    profit_by_arb_type: dict[str, float] = Field(default_factory=dict)

    final_equity: float = 0.0
    sharpe_ratio: float | None = None
    max_drawdown: float = 0.0
    win_rate: float = 0.0


class BacktestResult(BaseModel):
    """Full output of a completed backtest."""

    start_time: datetime
    end_time: datetime
    metrics: BacktestMetrics
    trade_log: list[FillResult] = Field(default_factory=list)
    settlement_log: list[SettlementResult] = Field(default_factory=list)
    final_portfolio: PortfolioState
    events_processed: int = 0
    run_duration_seconds: float = 0.0
