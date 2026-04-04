"""Tests for strategy interface and built-in wrappers."""

from datetime import datetime, timezone

import pytest

from simulation.models import (
    MarketSnapshot,
    MarketStatus,
    Observation,
    PortfolioState,
)
from simulation.strategy.interface import BaseStrategy
from simulation.strategy.wrappers import (
    GreedyArbStrategy,
    LoggingWrapper,
    NullStrategy,
    ThresholdArbStrategy,
)


def _now() -> datetime:
    return datetime(2024, 1, 2, tzinfo=timezone.utc)


def _empty_portfolio() -> PortfolioState:
    return PortfolioState(
        cash=10_000,
        locked_capital=0.0,
        total_equity=10_000,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        total_fees_paid=0.0,
    )


def _observation(
    opportunities=None,
    visible_markets=None,
) -> Observation:
    if opportunities is None:
        opportunities = []
    if visible_markets is None:
        visible_markets = {}
    return Observation(
        sim_time=_now(),
        visible_markets=visible_markets,
        opportunities=opportunities,
        portfolio=_empty_portfolio(),
    )


def _snap(platform: str, market_id: str) -> MarketSnapshot:
    return MarketSnapshot(
        platform=platform,
        market_id=market_id,
        question="Q?",
        outcomes=["Yes", "No"],
        best_bid={"Yes": 0.38, "No": 0.58},
        best_ask={"Yes": 0.40, "No": 0.60},
        last_traded={"Yes": 0.39, "No": 0.59},
        fees=0.02,
        status=MarketStatus.ACTIVE,
        snapshot_time=_now(),
    )


class TestNullStrategy:
    def test_always_returns_empty(self) -> None:
        strategy = NullStrategy()
        obs = _observation(opportunities=[{"type": "binary_pair", "net_profit_estimate": 0.1}])
        assert strategy.decide(obs) == []


class TestGreedyArbStrategy:
    def test_no_actions_without_opportunities(self) -> None:
        strategy = GreedyArbStrategy()
        obs = _observation()
        assert strategy.decide(obs) == []

    def test_enters_opportunity_above_threshold(self) -> None:
        snap_a = _snap("poly", "m1")
        snap_b = _snap("kalshi", "m2")
        opp = {
            "type": "binary_pair",
            "market_a": "poly::m1",
            "market_b": "kalshi::m2",
            "leg_a": {"outcome": "Yes", "price": 0.40},
            "leg_b": {"outcome": "No", "price": 0.55},
            "net_profit_estimate": 0.05,
        }
        obs = _observation(
            opportunities=[opp],
            visible_markets={"poly::m1": snap_a, "kalshi::m2": snap_b},
        )
        strategy = GreedyArbStrategy(min_net_profit=0.01)
        actions = strategy.decide(obs)
        assert len(actions) == 1
        assert len(actions[0].legs) == 2

    def test_skips_opportunity_below_threshold(self) -> None:
        snap_a = _snap("poly", "m1")
        snap_b = _snap("kalshi", "m2")
        opp = {
            "type": "binary_pair",
            "market_a": "poly::m1",
            "market_b": "kalshi::m2",
            "leg_a": {"outcome": "Yes", "price": 0.49},
            "leg_b": {"outcome": "No", "price": 0.50},
            "net_profit_estimate": 0.001,  # below 0.01 threshold
        }
        obs = _observation(
            opportunities=[opp],
            visible_markets={"poly::m1": snap_a, "kalshi::m2": snap_b},
        )
        strategy = GreedyArbStrategy(min_net_profit=0.01)
        assert strategy.decide(obs) == []

    def test_missing_market_in_visible_skipped(self) -> None:
        opp = {
            "type": "binary_pair",
            "market_a": "poly::unknown",
            "market_b": "kalshi::unknown2",
            "leg_a": {"outcome": "Yes", "price": 0.40},
            "leg_b": {"outcome": "No", "price": 0.55},
            "net_profit_estimate": 0.05,
        }
        obs = _observation(opportunities=[opp], visible_markets={})
        strategy = GreedyArbStrategy()
        assert strategy.decide(obs) == []


class TestThresholdArbStrategy:
    def test_respects_max_open_baskets(self) -> None:
        from simulation.models import ArbBasket, BasketStatus
        from datetime import datetime

        # Fill portfolio with open baskets
        open_baskets = [
            ArbBasket(
                basket_id=f"b{i}",
                legs=[],
                status=BasketStatus.OPEN,
                created_time=_now(),
            )
            for i in range(5)
        ]
        portfolio = PortfolioState(
            cash=5_000,
            locked_capital=5_000,
            total_equity=10_000,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_fees_paid=0.0,
            open_baskets=open_baskets,
        )
        obs = Observation(
            sim_time=_now(),
            visible_markets={},
            opportunities=[{"net_profit_estimate": 0.1, "type": "binary_pair"}],
            portfolio=portfolio,
        )
        strategy = ThresholdArbStrategy(max_open_baskets=5)
        assert strategy.decide(obs) == []


class TestLoggingWrapper:
    def test_delegates_to_inner(self) -> None:
        inner = NullStrategy()
        wrapped = LoggingWrapper(inner)
        obs = _observation()
        assert wrapped.decide(obs) == []

    def test_is_base_strategy(self) -> None:
        assert isinstance(LoggingWrapper(NullStrategy()), BaseStrategy)
