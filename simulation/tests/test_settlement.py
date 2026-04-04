"""Tests for settlement engine and payout calculation."""

from datetime import datetime, timezone

import pytest

from simulation.execution.settlement import SettlementEngine
from simulation.models import OrderSide, Position


def _now() -> datetime:
    return datetime(2025, 1, 1, tzinfo=timezone.utc)


def _position(
    outcome: str = "Yes",
    size: float = 10.0,
    entry_price: float = 0.40,
    basket_id: str = "b1",
    platform: str = "poly",
    market_id: str = "m1",
) -> Position:
    return Position(
        position_id=f"pos_{outcome}",
        platform=platform,
        market_id=market_id,
        outcome=outcome,
        side=OrderSide.BUY,
        size=size,
        entry_price=entry_price,
        entry_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        basket_id=basket_id,
    )


class TestSettlementEngine:
    def _engine(self) -> SettlementEngine:
        return SettlementEngine()

    def test_winning_outcome_full_payout(self) -> None:
        engine = self._engine()
        positions = [_position(outcome="Yes", size=10.0)]
        results = engine.settle_positions(
            positions=positions,
            platform="poly",
            market_id="m1",
            resolution_outcome="Yes",
            resolution_value=1.0,
            settlement_time=_now(),
        )
        assert len(results) == 1
        assert results[0].payout_per_share == 1.0
        assert results[0].gross_payout == 10.0
        assert results[0].net_payout == 10.0

    def test_losing_outcome_zero_payout(self) -> None:
        engine = self._engine()
        positions = [_position(outcome="Yes", size=10.0)]
        results = engine.settle_positions(
            positions=positions,
            platform="poly",
            market_id="m1",
            resolution_outcome="No",    # Yes loses
            resolution_value=1.0,
            settlement_time=_now(),
        )
        assert results[0].payout_per_share == 0.0
        assert results[0].gross_payout == 0.0

    def test_only_matching_market_settled(self) -> None:
        engine = self._engine()
        positions = [
            _position(outcome="Yes", platform="poly", market_id="m1"),
            _position(outcome="Yes", platform="kalshi", market_id="m2"),
        ]
        results = engine.settle_positions(
            positions=positions,
            platform="poly",
            market_id="m1",
            resolution_outcome="Yes",
            resolution_value=1.0,
            settlement_time=_now(),
        )
        assert len(results) == 1
        assert results[0].platform == "poly"

    def test_partial_payout_non_binary(self) -> None:
        """Non-binary resolution_value (e.g. 0.5) → partial payout."""
        engine = self._engine()
        positions = [_position(outcome="Yes", size=10.0)]
        results = engine.settle_positions(
            positions=positions,
            platform="poly",
            market_id="m1",
            resolution_outcome="Yes",
            resolution_value=0.5,
            settlement_time=_now(),
        )
        assert results[0].payout_per_share == 0.5
        assert results[0].gross_payout == 5.0

    def test_multiple_positions_settled(self) -> None:
        engine = self._engine()
        positions = [
            _position(outcome="Yes", size=5.0),
            _position(outcome="No", size=8.0),
        ]
        results = engine.settle_positions(
            positions=positions,
            platform="poly",
            market_id="m1",
            resolution_outcome="Yes",
            resolution_value=1.0,
            settlement_time=_now(),
        )
        assert len(results) == 2
        yes_result = next(r for r in results if r.outcome == "Yes")
        no_result = next(r for r in results if r.outcome == "No")
        assert yes_result.payout_per_share == 1.0
        assert no_result.payout_per_share == 0.0

    def test_empty_positions_returns_empty(self) -> None:
        engine = self._engine()
        results = engine.settle_positions(
            positions=[],
            platform="poly",
            market_id="m1",
            resolution_outcome="Yes",
            resolution_value=1.0,
            settlement_time=_now(),
        )
        assert results == []
