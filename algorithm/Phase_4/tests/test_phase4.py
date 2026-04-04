"""Tests for Phase 4 — Arbitrage Engine."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from algorithm.Phase_4.models import Direction, MarketInfo, MatchedPair, Platform
from algorithm.Phase_4.spread import compute_spread, two_sided_spread
from algorithm.Phase_4.kelly import expected_value, kelly_size
from algorithm.Phase_4.regression import (
    SpreadConvergenceModel,
    SpreadFeatures,
    extract_features,
    label_convergence,
)
from algorithm.Phase_4.engine import ArbitrageEngine, _align_and_spread


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_pair(
    price_a: float = 0.70,
    price_b: float = 0.63,
    similarity: float = 0.90,
) -> MatchedPair:
    return MatchedPair(
        pair_id="test-pair-001",
        market_a=MarketInfo(
            platform=Platform.POLYMARKET,
            market_id="mkt-a",
            yes_price=price_a,
            no_price=round(1.0 - price_a, 6),
            volume_24h=5000.0,
            close_date=datetime.utcnow() + timedelta(days=30),
        ),
        market_b=MarketInfo(
            platform=Platform.KALSHI,
            market_id="mkt-b",
            yes_price=price_b,
            no_price=round(1.0 - price_b, 6),
            volume_24h=3000.0,
            close_date=datetime.utcnow() + timedelta(days=30),
        ),
        similarity_score=similarity,
    )


# ── spread.py ─────────────────────────────────────────────────────────────────

class TestComputeSpread:
    def test_direction_buy_b_sell_a(self):
        pair = make_pair(price_a=0.70, price_b=0.63)
        spread, direction = compute_spread(pair)
        assert abs(spread - 0.07) < 1e-5
        assert direction == Direction.BUY_B_SELL_A

    def test_direction_buy_a_sell_b(self):
        pair = make_pair(price_a=0.55, price_b=0.65)
        spread, direction = compute_spread(pair)
        assert abs(spread - 0.10) < 1e-5
        assert direction == Direction.BUY_A_SELL_B

    def test_zero_spread(self):
        pair = make_pair(price_a=0.60, price_b=0.60)
        spread, direction = compute_spread(pair)
        assert spread == 0.0
        assert direction == Direction.BUY_B_SELL_A  # tie goes to BUY_B_SELL_A


class TestTwoSidedSpread:
    def test_profitable_arb(self):
        # YES@B=0.40, NO@A=(1-0.70)=0.30  →  cost=0.70  →  profit=0.30
        pair = make_pair(price_a=0.70, price_b=0.40)
        gs = two_sided_spread(pair)
        assert gs > 0

    def test_no_guaranteed_arb(self):
        # prices sum > 1 in all combinations
        pair = make_pair(price_a=0.60, price_b=0.55)
        gs = two_sided_spread(pair)
        # cost = 0.55 + 0.40 = 0.95  →  guaranteed = 0.05
        assert gs >= 0  # never negative

    def test_symmetric_prices(self):
        pair = make_pair(price_a=0.50, price_b=0.50)
        gs = two_sided_spread(pair)
        assert gs == 0.0


# ── kelly.py ──────────────────────────────────────────────────────────────────

class TestKellySize:
    def test_positive_edge(self):
        f, pos = kelly_size(
            convergence_prob=0.75,
            spread=0.10,
            bankroll=10_000.0,
        )
        assert f > 0
        assert pos > 0
        assert pos <= 1000.0  # 10% max cap

    def test_zero_spread(self):
        f, pos = kelly_size(convergence_prob=0.80, spread=0.0, bankroll=10_000.0)
        assert f == 0.0
        assert pos == 0.0

    def test_max_fraction_cap(self):
        _, pos = kelly_size(
            convergence_prob=0.99,
            spread=0.50,
            bankroll=10_000.0,
            max_frac=0.10,
        )
        assert pos <= 1000.0  # 10% of 10k

    def test_zero_bankroll(self):
        f, pos = kelly_size(convergence_prob=0.80, spread=0.10, bankroll=0.0)
        assert pos == 0.0


class TestExpectedValue:
    def test_positive_ev(self):
        ev = expected_value(
            convergence_prob=0.80,
            spread=0.10,
            position_usd=1000.0,
        )
        assert ev > 0

    def test_zero_position(self):
        ev = expected_value(convergence_prob=0.80, spread=0.10, position_usd=0.0)
        assert ev == 0.0

    def test_low_prob_negative_ev(self):
        ev = expected_value(
            convergence_prob=0.10,
            spread=0.05,
            position_usd=1000.0,
        )
        assert ev < 0


# ── regression.py ─────────────────────────────────────────────────────────────

class TestExtractFeatures:
    def test_short_series_fallback(self):
        series = np.array([0.05])
        f = extract_features(series, [], 100.0, 100.0, None)
        assert f.current_spread == pytest.approx(0.05)
        assert f.spread_velocity == 0.0

    def test_full_series(self):
        series = np.array([0.05, 0.06, 0.07, 0.06, 0.08, 0.07, 0.09])
        ts = [datetime.utcnow() - timedelta(hours=i) for i in range(7, 0, -1)]
        f = extract_features(series, ts, 500.0, 500.0, None)
        assert f.current_spread == pytest.approx(series[-1])
        assert f.mean_spread == pytest.approx(np.mean(series))
        assert f.spread_volatility > 0

    def test_volume_ratio_clamped(self):
        series = np.array([0.05, 0.06, 0.07])
        f = extract_features(series, [], 10000.0, 1.0, None)
        assert f.volume_ratio <= 10.0


class TestSpreadConvergenceModel:
    def test_heuristic_large_spread(self):
        model = SpreadConvergenceModel()
        f = SpreadFeatures(
            current_spread=0.15,
            mean_spread=0.08,
            spread_velocity=-0.01,
            spread_volatility=0.02,
            volume_ratio=1.0,
            time_to_close_days=30.0,
            spread_z_score=2.5,
            max_spread_lookback=0.18,
        )
        prob = model.predict_convergence_prob(f)
        assert 0.5 < prob <= 1.0  # large spread + falling + high z-score = bullish

    def test_heuristic_small_spread(self):
        model = SpreadConvergenceModel()
        f = SpreadFeatures(
            current_spread=0.01,
            mean_spread=0.01,
            spread_velocity=0.001,
            spread_volatility=0.005,
            volume_ratio=1.0,
            time_to_close_days=200.0,
            spread_z_score=0.1,
            max_spread_lookback=0.02,
        )
        prob = model.predict_convergence_prob(f)
        assert 0.0 < prob < 0.8  # small spread, slight upward velocity


class TestLabelConvergence:
    def test_converging_series(self):
        # series[2]=0.08 → series[2+3]=0.01, drop of 87.5% ≥ 50% → label=1
        series = np.array([0.10, 0.09, 0.08, 0.07, 0.03, 0.01])
        labels = label_convergence(series, lookahead=3, threshold_pct=0.50)
        assert labels[2] == 1  # 0.08 → 0.01 is an 87.5% drop

    def test_flat_series(self):
        series = np.ones(10) * 0.05
        labels = label_convergence(series, lookahead=3, threshold_pct=0.50)
        assert all(labels == 0)  # flat spread never converges by 50%


# ── engine.py ─────────────────────────────────────────────────────────────────

class TestArbitrageEngine:
    def test_score_pair_produces_signal(self):
        engine = ArbitrageEngine(bankroll=10_000.0)
        pair = make_pair(price_a=0.70, price_b=0.55, similarity=0.92)
        signal = engine.score_pair(pair)
        # With a 15% spread and high similarity, should produce a signal
        assert signal is not None
        assert signal.raw_spread == pytest.approx(0.15)
        assert signal.confidence > 0
        assert signal.expected_profit != 0

    def test_score_pair_below_threshold(self):
        engine = ArbitrageEngine(bankroll=10_000.0)
        pair = make_pair(price_a=0.60, price_b=0.595)  # 0.5% spread
        signal = engine.score_pair(pair)
        assert signal is None  # below MIN_SPREAD

    def test_score_pairs_sorted_by_ev(self):
        engine = ArbitrageEngine(bankroll=10_000.0)
        pairs = [
            make_pair(price_a=0.70, price_b=0.55, similarity=0.95),
            make_pair(price_a=0.65, price_b=0.50, similarity=0.88),
        ]
        # Assign unique pair IDs
        pairs[0] = pairs[0].model_copy(update={"pair_id": "pair-high"})
        pairs[1] = pairs[1].model_copy(update={"pair_id": "pair-low"})

        signals = engine.score_pairs(pairs)
        if len(signals) >= 2:
            assert signals[0].expected_profit >= signals[1].expected_profit

    def test_align_and_spread(self):
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        hist_a = [
            {"timestamp": now - timedelta(hours=2), "yes_price": 0.60},
            {"timestamp": now - timedelta(hours=1), "yes_price": 0.62},
            {"timestamp": now, "yes_price": 0.65},
        ]
        hist_b = [
            {"timestamp": now - timedelta(hours=2), "yes_price": 0.55},
            {"timestamp": now - timedelta(hours=1), "yes_price": 0.57},
            {"timestamp": now, "yes_price": 0.60},
        ]
        spreads, ts = _align_and_spread(hist_a, hist_b)
        assert len(spreads) == 3
        np.testing.assert_allclose(spreads, [0.05, 0.05, 0.05])
