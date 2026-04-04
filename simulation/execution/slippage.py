"""
Slippage model.

Computes the price impact of a trade given visible liquidity.

Three models by realism mode:

OPTIMISTIC  — zero slippage; fill at best ask/bid
REALISTIC   — linear impact model: price worsens as order consumes depth
PESSIMISTIC — aggressive impact model; assumes thin books and adverse conditions
"""

from __future__ import annotations

import math

from simulation.config import SimulationConfig
from simulation.models import MarketSnapshot, OrderSide, RealismMode


class SlippageModel:
    def __init__(self, config: SimulationConfig) -> None:
        self._exec_params = config.execution_params()
        self._mode = config.realism_mode

    def adjusted_price(
        self,
        side: OrderSide,
        outcome: str,
        requested_size: float,
        snapshot: MarketSnapshot | None,
    ) -> tuple[float, float, float]:
        """
        Return (fill_price, filled_size, slippage_cost).

        fill_price  — execution price after slippage
        filled_size — how much actually fills (may be less than requested)
        slippage_cost — dollar cost of slippage
        """
        if self._mode == RealismMode.OPTIMISTIC or snapshot is None:
            base = self._base_price(side, outcome, snapshot)
            return base, requested_size, 0.0

        if self._mode == RealismMode.REALISTIC:
            return self._linear_impact(side, outcome, requested_size, snapshot)

        # Pessimistic
        return self._pessimistic_impact(side, outcome, requested_size, snapshot)

    # ------------------------------------------------------------------

    def _base_price(self, side: OrderSide, outcome: str, snap: MarketSnapshot | None) -> float:
        if snap is None:
            return 0.5
        if side == OrderSide.BUY:
            return snap.best_ask.get(outcome) or snap.last_traded.get(outcome) or 0.5
        return snap.best_bid.get(outcome) or snap.last_traded.get(outcome) or 0.5

    def _linear_impact(
        self,
        side: OrderSide,
        outcome: str,
        size: float,
        snap: MarketSnapshot,
    ) -> tuple[float, float, float]:
        """
        Walk the visible orderbook. If depth is insufficient, fill what's available
        and mark the rest as unfilled (partial fill).
        """
        if side == OrderSide.BUY:
            levels = snap.asks.get(outcome, [])
        else:
            levels = snap.bids.get(outcome, [])

        if not levels:
            # No depth data — apply config slippage_bps to best price
            base = self._base_price(side, outcome, snap)
            slip_rate = self._exec_params.slippage_bps / 10_000
            if side == OrderSide.BUY:
                fill_price = min(0.999, base * (1 + slip_rate))
            else:
                fill_price = max(0.001, base * (1 - slip_rate))
            slippage_cost = abs(fill_price - base) * size
            return fill_price, size, slippage_cost

        # Walk the book
        remaining = size
        total_cost = 0.0
        filled = 0.0

        for level in sorted(levels, key=lambda lv: lv.price,
                            reverse=(side == OrderSide.SELL)):
            if remaining <= 0:
                break
            take = min(remaining, level.size)
            total_cost += take * level.price
            filled += take
            remaining -= take

        if filled == 0:
            base = self._base_price(side, outcome, snap)
            return base, 0.0, 0.0

        avg_price = total_cost / filled
        base_price = self._base_price(side, outcome, snap)
        slippage_cost = abs(avg_price - base_price) * filled
        return avg_price, filled, slippage_cost

    def _pessimistic_impact(
        self,
        side: OrderSide,
        outcome: str,
        size: float,
        snap: MarketSnapshot,
    ) -> tuple[float, float, float]:
        fill_price, filled_size, slip_cost = self._linear_impact(side, outcome, size, snap)

        # Extra penalty on top of linear model
        extra_slip = self._exec_params.slippage_bps / 10_000 * 2
        if side == OrderSide.BUY:
            fill_price = min(0.999, fill_price * (1 + extra_slip))
        else:
            fill_price = max(0.001, fill_price * (1 - extra_slip))

        # Pessimistic: only fill a fraction of the available size
        filled_size *= self._exec_params.partial_fill_fraction
        additional_slip = abs(fill_price - (slip_cost / size if size > 0 else fill_price)) * filled_size
        return fill_price, filled_size, slip_cost + additional_slip
