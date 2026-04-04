"""Tests for Phase 5 — Live Validation."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from algorithm.Phase_4.models import ArbitrageSignal, Direction, Platform
from algorithm.Phase_5.liquidity import LiquidityCheck, adjust_size_for_liquidity, check_liquidity
from algorithm.Phase_5.correlation import compute_correlation_from_arrays
from algorithm.Phase_5.price_checker import check_spread_still_exists
from algorithm.Phase_5.validator import TradeValidator
from algorithm.Phase_5.models import TradeAction, ValidatedOpportunity


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_signal(
    price_a: float = 0.70,
    price_b: float = 0.55,
    direction: Direction = Direction.BUY_B_SELL_A,
    size: float = 500.0,
    confidence: float = 0.70,
) -> ArbitrageSignal:
    return ArbitrageSignal(
        pair_id="test-signal-001",
        market_a_id="mkt-a",
        market_b_id="mkt-b",
        platform_a=Platform.POLYMARKET,
        platform_b=Platform.KALSHI,
        price_a=price_a,
        price_b=price_b,
        raw_spread=abs(price_a - price_b),
        direction=direction,
        regression_convergence_prob=0.70,
        expected_profit=25.0,
        kelly_fraction=0.05,
        recommended_size_usd=size,
        confidence=confidence,
    )


# ── liquidity.py ──────────────────────────────────────────────────────────────

class TestCheckLiquidity:
    def test_sufficient_liquidity(self):
        result = check_liquidity(10_000.0, 8_000.0, 500.0)
        assert result.sufficient
        assert result.reason == "OK"

    def test_zero_liquidity_a(self):
        result = check_liquidity(0.0, 8_000.0, 500.0)
        assert not result.sufficient
        assert "zero liquidity" in result.reason.lower()

    def test_zero_liquidity_b(self):
        result = check_liquidity(10_000.0, 0.0, 500.0)
        assert not result.sufficient

    def test_position_too_large(self):
        # 10% of 1000 = 100 < 500
        result = check_liquidity(1_000.0, 1_000.0, 500.0)
        assert not result.sufficient
        assert "exceeds" in result.reason

    def test_exactly_at_limit(self):
        # 10% of 10000 = 1000 == 1000 (not exceeding)
        result = check_liquidity(10_000.0, 10_000.0, 1_000.0)
        assert result.sufficient


class TestAdjustSizeForLiquidity:
    def test_no_adjustment_needed(self):
        size = adjust_size_for_liquidity(500.0, 10_000.0, 10_000.0)
        assert size == 500.0

    def test_capped_by_liquidity(self):
        size = adjust_size_for_liquidity(1_000.0, 5_000.0, 5_000.0)
        assert size == pytest.approx(500.0)  # 10% of 5000

    def test_zero_liquidity_returns_zero(self):
        size = adjust_size_for_liquidity(500.0, 0.0, 5_000.0)
        assert size == 0.0


# ── correlation.py ────────────────────────────────────────────────────────────

class TestComputeCorrelationFromArrays:
    def test_perfectly_correlated(self):
        prices = np.linspace(0.40, 0.70, 20)
        score, is_valid = compute_correlation_from_arrays(prices, prices)
        assert score > 0.80
        assert is_valid

    def test_negatively_correlated(self):
        a = np.linspace(0.40, 0.70, 20)
        b = np.linspace(0.70, 0.40, 20)
        score, is_valid = compute_correlation_from_arrays(a, b)
        assert score < 0
        assert not is_valid

    def test_insufficient_points(self):
        a = np.array([0.5, 0.6])
        b = np.array([0.5, 0.6])
        score, is_valid = compute_correlation_from_arrays(a, b, min_points=10)
        assert score == 0.0
        assert is_valid  # benefit of the doubt

    def test_uncorrelated_random(self):
        rng = np.random.default_rng(42)
        a = rng.uniform(0.3, 0.7, 30)
        b = rng.uniform(0.3, 0.7, 30)
        score, is_valid = compute_correlation_from_arrays(a, b)
        # Random series should not pass strict correlation test
        assert not is_valid or abs(score) < 0.60


# ── price_checker.py ──────────────────────────────────────────────────────────

class TestCheckSpreadStillExists:
    def test_spread_still_there(self):
        sig = make_signal(price_a=0.70, price_b=0.55)
        live_spread, ok = check_spread_still_exists(sig, 0.69, 0.54, min_spread=0.02)
        assert ok
        assert live_spread == pytest.approx(0.15)

    def test_spread_vanished(self):
        sig = make_signal(price_a=0.70, price_b=0.55)
        live_spread, ok = check_spread_still_exists(sig, 0.61, 0.60, min_spread=0.02)
        assert not ok
        assert live_spread == pytest.approx(0.01)

    def test_exactly_at_min_spread(self):
        sig = make_signal()
        _, ok = check_spread_still_exists(sig, 0.62, 0.60, min_spread=0.02)
        assert ok


# ── validator.py ──────────────────────────────────────────────────────────────

class TestTradeValidator:
    def _make_validator_no_db(self) -> TradeValidator:
        """Validator with DB calls patched out."""
        return TradeValidator(min_spread=0.02)

    def test_validate_no_live_prices_falls_back(self):
        """When live prices are unavailable, validator falls back to Phase 4 prices."""
        validator = self._make_validator_no_db()
        sig = make_signal(price_a=0.70, price_b=0.55, size=0.0)  # size=0 → not executable

        with patch("algorithm.Phase_5.validator.fetch_live_price", return_value=None), \
             patch.object(validator, "_get_liquidity", return_value=(0.0, 0.0)):
            result = validator.validate(sig)

        # Not executable because size=0 and liquidity=0
        assert isinstance(result, ValidatedOpportunity)
        assert not result.executable

    def test_validate_executable_path(self):
        """Signal with good spread, direction, and liquidity is executable."""
        validator = self._make_validator_no_db()
        sig = make_signal(price_a=0.70, price_b=0.55, size=500.0)

        with patch("algorithm.Phase_5.validator.fetch_live_price", side_effect=[0.70, 0.55]), \
             patch.object(validator, "_get_liquidity", return_value=(50_000.0, 50_000.0)), \
             patch(
                 "algorithm.Phase_5.validator.compute_price_correlation",
                 return_value=(0.0, True),
             ):
            result = validator.validate(sig)

        assert result.executable
        assert len(result.actions) == 2
        assert result.rejection_reasons == []

    def test_validate_direction_reversed(self):
        """Signal rejected when live prices flip the direction."""
        validator = self._make_validator_no_db()
        # Phase 4 said BUY_B_SELL_A (A > B), but live shows A < B
        sig = make_signal(
            price_a=0.70, price_b=0.55, direction=Direction.BUY_B_SELL_A, size=500.0
        )

        with patch("algorithm.Phase_5.validator.fetch_live_price", side_effect=[0.50, 0.60]), \
             patch.object(validator, "_get_liquidity", return_value=(50_000.0, 50_000.0)), \
             patch(
                 "algorithm.Phase_5.validator.compute_price_correlation",
                 return_value=(0.0, True),
             ):
            result = validator.validate(sig)

        assert not result.executable
        assert any("Direction reversed" in r for r in result.rejection_reasons)

    def test_build_actions_buy_b_sell_a(self):
        sig = make_signal(direction=Direction.BUY_B_SELL_A)
        actions = TradeValidator._build_actions(sig, 0.70, 0.55, 1000.0)
        assert len(actions) == 2
        buy_b = next(a for a in actions if a.platform == Platform.KALSHI)
        sell_a = next(a for a in actions if a.platform == Platform.POLYMARKET)
        assert buy_b.side == "yes"
        assert sell_a.side == "no"
        assert buy_b.amount_usd == sell_a.amount_usd == 500.0

    def test_build_actions_buy_a_sell_b(self):
        sig = make_signal(direction=Direction.BUY_A_SELL_B)
        actions = TradeValidator._build_actions(sig, 0.55, 0.70, 1000.0)
        assert len(actions) == 2
        buy_a = next(a for a in actions if a.platform == Platform.POLYMARKET)
        sell_b = next(a for a in actions if a.platform == Platform.KALSHI)
        assert buy_a.side == "yes"
        assert sell_b.side == "no"

    def test_validate_batch(self):
        validator = self._make_validator_no_db()
        signals = [
            make_signal(price_a=0.70, price_b=0.55, size=500.0),
            make_signal(price_a=0.65, price_b=0.50, size=300.0),
        ]
        signals[1] = signals[1].model_copy(update={"pair_id": "pair-2"})

        with patch("algorithm.Phase_5.validator.fetch_live_price", side_effect=[
                0.70, 0.55,  # signal 1
                0.65, 0.50,  # signal 2
            ]), \
             patch.object(validator, "_get_liquidity", return_value=(50_000.0, 50_000.0)), \
             patch(
                 "algorithm.Phase_5.validator.compute_price_correlation",
                 return_value=(0.0, True),
             ):
            results = validator.validate_batch(signals)

        assert len(results) == 2
