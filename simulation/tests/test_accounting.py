"""Tests for portfolio accounting: Account, positions, baskets."""

import uuid
from datetime import datetime, timezone

import pytest

from simulation.models import (
    ArbBasket,
    BasketLeg,
    BasketStatus,
    FillResult,
    FillStatus,
    MarketState,
    MarketStatus,
    MarketSnapshot,
    OrderSide,
)
from simulation.portfolio.account import Account
from simulation.portfolio.positions import PositionRegistry


def _now() -> datetime:
    return datetime(2024, 6, 1, tzinfo=timezone.utc)


def _fill(
    basket_id: str = "basket1",
    yes_price: float = 0.40,
    no_price: float = 0.55,
    size: float = 10.0,
    status: FillStatus = FillStatus.FILLED,
) -> FillResult:
    leg_a = BasketLeg(
        leg_id="leg_a",
        platform="poly",
        market_id="m1",
        outcome="Yes",
        side=OrderSide.BUY,
        requested_size=size,
        fill_price=yes_price,
        filled_size=size,
        fees_paid=0.01,
        fill_status=FillStatus.FILLED,
        fill_time=_now(),
    )
    leg_b = BasketLeg(
        leg_id="leg_b",
        platform="kalshi",
        market_id="m2",
        outcome="No",
        side=OrderSide.BUY,
        requested_size=size,
        fill_price=no_price,
        filled_size=size,
        fees_paid=0.01,
        fill_status=FillStatus.FILLED,
        fill_time=_now(),
    )
    locked = (yes_price + no_price) * size
    return FillResult(
        action_id=str(uuid.uuid4()),
        basket_id=basket_id,
        legs=[leg_a, leg_b],
        fill_status=status,
        total_fees=0.02,
        total_slippage_cost=0.0,
        locked_capital=locked,
        expected_profit=1.0 * size - locked,
        fill_time=_now(),
    )


class TestAccount:
    def test_initial_state(self) -> None:
        account = Account(initial_capital=5_000)
        state = account.get_portfolio_state()
        assert state.cash == 5_000
        assert state.realized_pnl == 0.0
        assert state.locked_capital == 0.0

    def test_apply_fill_reduces_cash(self) -> None:
        account = Account(10_000)
        fill = _fill(yes_price=0.40, no_price=0.55, size=10.0)
        account.apply_fill(fill)
        # locked = (0.40+0.55)*10 = 9.50
        assert account.cash == pytest.approx(10_000 - 9.50, abs=0.01)
        assert account.locked_capital == pytest.approx(9.50, abs=0.01)

    def test_rejected_fill_no_cash_change(self) -> None:
        account = Account(10_000)
        fill = _fill(status=FillStatus.REJECTED)
        fill.locked_capital = 0.0
        account.apply_fill(fill)
        assert account.cash == 10_000

    def test_settle_winning_position(self) -> None:
        account = Account(10_000)
        fill = _fill(basket_id="b1", yes_price=0.40, no_price=0.55, size=10.0)
        account.apply_fill(fill)
        cash_before = account.cash

        # Yes wins → payout = 1.0 per share
        settlements = account.settle_market(
            platform="poly",
            market_id="m1",
            resolution_outcome="Yes",
            resolution_value=1.0,
            settlement_time=_now(),
        )
        assert len(settlements) > 0
        assert account.cash > cash_before  # received payout

    def test_settle_losing_position(self) -> None:
        account = Account(10_000)
        fill = _fill(basket_id="b1", yes_price=0.40, no_price=0.55, size=10.0)
        account.apply_fill(fill)
        cash_before = account.cash

        # Yes loses → payout = 0
        settlements = account.settle_market(
            platform="poly",
            market_id="m1",
            resolution_outcome="No",    # Yes position loses
            resolution_value=1.0,
            settlement_time=_now(),
        )
        # Cash unchanged for the Yes position (payout = 0)
        assert account.cash == cash_before

    def test_reset_clears_state(self) -> None:
        account = Account(10_000)
        fill = _fill()
        account.apply_fill(fill)
        account.reset(10_000)
        state = account.get_portfolio_state()
        assert state.cash == 10_000
        assert state.locked_capital == 0.0

    def test_mark_to_market_updates_unrealized(self) -> None:
        account = Account(10_000)
        fill = _fill(yes_price=0.40, size=10.0)
        account.apply_fill(fill)

        # Simulate price moving up to 0.60
        from simulation.models import MarketSnapshot
        snap = MarketSnapshot(
            platform="poly",
            market_id="m1",
            question="Q?",
            outcomes=["Yes", "No"],
            best_bid={"Yes": 0.59},
            best_ask={"Yes": 0.61},
            last_traded={"Yes": 0.60},
            snapshot_time=_now(),
        )
        state = MarketState(
            market_id="m1",
            platform="poly",
            latest_snapshot=snap,
            last_update_time=_now(),
            status=MarketStatus.ACTIVE,
        )
        account.mark_to_market({"poly::m1": state})
        assert account.unrealized_pnl > 0


class TestPositionRegistry:
    def test_open_position_from_fill(self) -> None:
        reg = PositionRegistry()
        fill = _fill()
        positions = reg.open_from_fill(fill)
        assert len(positions) == 2

    def test_positions_for_market(self) -> None:
        reg = PositionRegistry()
        reg.open_from_fill(_fill())
        positions = reg.positions_for_market("poly", "m1")
        assert len(positions) == 1

    def test_close_position(self) -> None:
        reg = PositionRegistry()
        positions = reg.open_from_fill(_fill())
        pos_id = positions[0].position_id
        reg.close_position(pos_id, close_price=1.0, close_time=_now())
        assert len(reg.all_open()) == 1  # other position still open
        assert len(reg.all_closed()) == 1
