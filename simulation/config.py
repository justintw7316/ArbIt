"""
Simulation configuration — all tunable parameters in one place.

Supports three realism modes that override execution defaults:
  optimistic   — best-case fills, zero slippage, minimum fees
  realistic    — modeled slippage, standard fees, modest latency
  pessimistic  — high slippage, max fees, conservative partial fills
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from pydantic import BaseModel, Field

from simulation.models import RealismMode


class RealisticExecutionParams(BaseModel):
    """Per-mode execution parameter overrides."""

    fee_bps: float            # basis points per leg
    slippage_bps: float       # basis points slippage
    latency_ms: float         # simulated order latency
    fill_probability: float   # P(fill | order submitted), for pessimistic partial modelling
    partial_fill_fraction: float = 1.0  # expected fraction filled in partial scenario


REALISM_DEFAULTS: dict[RealismMode, RealisticExecutionParams] = {
    RealismMode.OPTIMISTIC: RealisticExecutionParams(
        fee_bps=50.0,
        slippage_bps=0.0,
        latency_ms=0.0,
        fill_probability=1.0,
        partial_fill_fraction=1.0,
    ),
    RealismMode.REALISTIC: RealisticExecutionParams(
        fee_bps=100.0,
        slippage_bps=50.0,
        latency_ms=200.0,
        fill_probability=0.85,
        partial_fill_fraction=0.9,
    ),
    RealismMode.PESSIMISTIC: RealisticExecutionParams(
        fee_bps=200.0,
        slippage_bps=150.0,
        latency_ms=500.0,
        fill_probability=0.65,
        partial_fill_fraction=0.7,
    ),
}


class SimulationConfig(BaseModel):
    """Top-level configuration for a backtest run."""

    # Time range (None = use data bounds)
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Capital limits
    initial_capital: float = Field(default=10_000.0, gt=0)
    max_position_size: float = Field(default=1_000.0, gt=0)   # per market
    max_basket_size: float = Field(default=500.0, gt=0)        # per basket
    max_open_baskets: int = 20

    # Execution realism
    realism_mode: RealismMode = RealismMode.REALISTIC

    # Per-mode overrides (if None, uses REALISM_DEFAULTS)
    fee_bps: float | None = None
    slippage_bps: float | None = None
    latency_ms: float | None = None

    # Trade filters
    min_trade_size: float = 1.0
    min_profit_threshold: float = 0.005   # 0.5% minimum net profit
    # Prediction markets may go hours/days between updates — default 7 days
    stale_quote_tolerance_seconds: float = 86400.0 * 7

    # Fill behaviour
    partial_fill_enabled: bool = True

    # Data
    data_path: str = "simulation/data/historical"

    # Reporting
    equity_curve_resolution_minutes: int = 60  # how often to sample equity

    def execution_params(self) -> RealisticExecutionParams:
        """Return effective execution params, applying any explicit overrides."""
        base = REALISM_DEFAULTS[self.realism_mode]
        return RealisticExecutionParams(
            fee_bps=self.fee_bps if self.fee_bps is not None else base.fee_bps,
            slippage_bps=self.slippage_bps if self.slippage_bps is not None else base.slippage_bps,
            latency_ms=self.latency_ms if self.latency_ms is not None else base.latency_ms,
            fill_probability=base.fill_probability,
            partial_fill_fraction=base.partial_fill_fraction,
        )


def default_config() -> SimulationConfig:
    return SimulationConfig()
