"""
Portfolio-level settlement helpers.

Provide summary views of settlement activity.
"""

from __future__ import annotations

from simulation.models import SettlementResult


def total_gross_payout(settlements: list[SettlementResult]) -> float:
    return sum(s.gross_payout for s in settlements)


def total_net_payout(settlements: list[SettlementResult]) -> float:
    return sum(s.net_payout for s in settlements)


def settlements_for_market(
    settlements: list[SettlementResult], platform: str, market_id: str
) -> list[SettlementResult]:
    return [s for s in settlements if s.platform == platform and s.market_id == market_id]


def settlements_for_basket(
    settlements: list[SettlementResult], basket_id: str
) -> list[SettlementResult]:
    return [s for s in settlements if s.basket_id == basket_id]
