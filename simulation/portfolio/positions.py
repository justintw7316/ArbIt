"""
Position registry — tracks all open and closed positions.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from simulation.models import FillResult, FillStatus, MarketState, OrderSide, Position


class PositionRegistry:
    """Maintains open and closed positions."""

    def __init__(self) -> None:
        self._open: dict[str, Position] = {}   # position_id -> Position
        self._closed: list[Position] = []

    def open_from_fill(self, fill: FillResult) -> list[Position]:
        """Create positions from a FillResult's filled legs."""
        new_positions: list[Position] = []
        for leg in fill.legs:
            if leg.fill_status not in (FillStatus.FILLED, FillStatus.PARTIAL):
                continue
            if (leg.fill_price is None) or (leg.filled_size <= 0):
                continue
            pos = Position(
                position_id=str(uuid.uuid4()),
                platform=leg.platform,
                market_id=leg.market_id,
                outcome=leg.outcome,
                side=leg.side,
                size=leg.filled_size,
                entry_price=leg.fill_price,
                entry_time=fill.fill_time,
                current_price=leg.fill_price,
                fees_paid=leg.fees_paid,
                basket_id=fill.basket_id,
            )
            self._open[pos.position_id] = pos
            new_positions.append(pos)
        return new_positions

    def mark_to_market(self, market_states: dict[str, MarketState]) -> None:
        """Update current_price for all open positions."""
        for pos in self._open.values():
            mkey = f"{pos.platform}::{pos.market_id}"
            state = market_states.get(mkey)
            if state and state.latest_snapshot:
                snap = state.latest_snapshot
                mid = snap.mid_price(pos.outcome)
                if mid is not None:
                    pos.current_price = mid

    def close_position(
        self, position_id: str, close_price: float, close_time: datetime
    ) -> Position | None:
        pos = self._open.pop(position_id, None)
        if pos:
            pos.current_price = close_price
            self._closed.append(pos)
        return pos

    def positions_for_market(
        self, platform: str, market_id: str
    ) -> list[Position]:
        return [
            p for p in self._open.values()
            if p.platform == platform and p.market_id == market_id
        ]

    def all_open(self) -> list[Position]:
        return list(self._open.values())

    def all_closed(self) -> list[Position]:
        return list(self._closed)

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self._open.values())

    def reset(self) -> None:
        self._open.clear()
        self._closed.clear()
