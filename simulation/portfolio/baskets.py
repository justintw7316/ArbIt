"""
Portfolio-level basket analytics helpers.

Thin wrappers around BasketTracker for external callers (analytics, reporting).
"""

from __future__ import annotations

from simulation.execution.baskets import BasketTracker
from simulation.models import ArbBasket, BasketStatus


def get_open_baskets(tracker: BasketTracker) -> list[ArbBasket]:
    return [b for b in tracker.all_open() if b.status in (BasketStatus.OPEN, BasketStatus.PARTIAL)]


def get_closed_baskets(tracker: BasketTracker) -> list[ArbBasket]:
    return tracker.all_closed()


def get_failed_baskets(tracker: BasketTracker) -> list[ArbBasket]:
    return [b for b in tracker.all_closed() if b.status == BasketStatus.FAILED]


def total_realized_pnl(tracker: BasketTracker) -> float:
    return sum(
        b.realized_pnl or 0.0
        for b in tracker.all_closed()
        if b.status == BasketStatus.CLOSED
    )


def profit_by_arb_type(tracker: BasketTracker) -> dict[str, float]:
    result: dict[str, float] = {}
    for b in tracker.all_closed():
        if b.status == BasketStatus.CLOSED and b.realized_pnl is not None:
            result[b.arb_type] = result.get(b.arb_type, 0.0) + b.realized_pnl
    return result
