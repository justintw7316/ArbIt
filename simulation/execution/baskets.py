"""
Basket tracker — tracks open and closed arbitrage baskets through their lifecycle.

A basket moves through states:
  PENDING → (all fills arrive) → OPEN → (market resolves) → CLOSED
  PENDING → (partial/failed fills) → PARTIAL / FAILED
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime

from simulation.models import (
    ArbBasket,
    BasketLeg,
    BasketStatus,
    FillResult,
    FillStatus,
    SettlementResult,
)

logger = logging.getLogger(__name__)


class BasketTracker:
    """Maintains the state of all open and closed baskets."""

    def __init__(self) -> None:
        self._open: dict[str, ArbBasket] = {}
        self._closed: list[ArbBasket] = []

    def open_basket(
        self, fill_result: FillResult, created_time: datetime
    ) -> ArbBasket | None:
        """Register a new basket from a FillResult. Returns the basket."""
        if fill_result.fill_status == FillStatus.REJECTED:
            return None

        status = BasketStatus.PARTIAL if fill_result.fill_status == FillStatus.PARTIAL else BasketStatus.OPEN
        open_time = fill_result.fill_time if status == BasketStatus.OPEN else None

        basket = ArbBasket(
            basket_id=fill_result.basket_id,
            legs=fill_result.legs,
            status=status,
            created_time=created_time,
            open_time=open_time,
            locked_capital=fill_result.locked_capital,
            expected_profit=fill_result.expected_profit,
            total_fees=fill_result.total_fees,
            total_slippage_cost=fill_result.total_slippage_cost,
        )
        self._open[basket.basket_id] = basket
        logger.debug("Basket opened: %s status=%s", basket.basket_id, status)
        return basket

    def get_open(self, basket_id: str) -> ArbBasket | None:
        return self._open.get(basket_id)

    def all_open(self) -> list[ArbBasket]:
        return list(self._open.values())

    def all_closed(self) -> list[ArbBasket]:
        return list(self._closed)

    def close_basket(
        self,
        basket_id: str,
        realized_pnl: float,
        close_time: datetime,
    ) -> ArbBasket | None:
        basket = self._open.pop(basket_id, None)
        if basket is None:
            return None
        basket.status = BasketStatus.CLOSED
        basket.realized_pnl = realized_pnl
        basket.close_time = close_time
        self._closed.append(basket)
        logger.info(
            "Basket closed: %s pnl=%.4f",
            basket_id, realized_pnl,
        )
        return basket

    def fail_basket(self, basket_id: str, reason: str = "") -> ArbBasket | None:
        basket = self._open.pop(basket_id, None)
        if basket is None:
            return None
        basket.status = BasketStatus.FAILED
        basket.notes = reason
        self._closed.append(basket)
        return basket

    def mark_partial_complete(
        self, basket_id: str, open_time: datetime
    ) -> ArbBasket | None:
        basket = self._open.get(basket_id)
        if basket is None:
            return None
        basket.status = BasketStatus.OPEN
        basket.open_time = open_time
        return basket

    def reset(self) -> None:
        self._open.clear()
        self._closed.clear()
