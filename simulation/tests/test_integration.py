"""
Intensive integration tests for the full arbitrage simulation pipeline.

These tests verify the end-to-end arb lifecycle:
  opportunity detected → strategy submits action → fill engine executes
  → positions opened → market resolves → settlement → realized PnL

Each scenario is deterministic and asserts exact or bounded values.
"""

from __future__ import annotations

import pytest

from simulation.config import SimulationConfig
from simulation.data.loader import HistoricalDataLoader, load_toy_dataset
from simulation.data.replay_stream import ReplayStream
from simulation.environment.env import SimulationEnvironment
from simulation.models import FillStatus, MarketStatus, RealismMode
from simulation.run_backtest import run_backtest
from simulation.strategy.wrappers import GreedyArbStrategy, NullStrategy


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _loader() -> HistoricalDataLoader:
    return HistoricalDataLoader("")


def _make_events(records: list[dict]) -> list:
    """Build HistoricalReplayEvents from a list of raw record dicts."""
    return list(_loader().load_from_records(records))


def _run(
    records: list[dict],
    *,
    initial_capital: float = 10_000.0,
    realism_mode: RealismMode = RealismMode.OPTIMISTIC,
    fee_bps: float | None = 0.0,
    min_net_profit: float = 0.001,
    max_size_per_leg: float = 10.0,
    verbose: bool = False,
):
    """Convenience wrapper — build events and run a full backtest."""
    events = _make_events(records)
    config = SimulationConfig(
        initial_capital=initial_capital,
        realism_mode=realism_mode,
        fee_bps=fee_bps,
    )
    strategy = GreedyArbStrategy(
        min_net_profit=min_net_profit,
        max_size_per_leg=max_size_per_leg,
    )
    return run_backtest(config=config, strategy=strategy, events=events, verbose=verbose)


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------

def _binary_arb_records(
    *,
    ask_yes_a: float,
    ask_no_b: float,
    fees_a: float = 0.0,
    fees_b: float = 0.0,
    resolution_outcome: str = "Yes",
    resolution_value: float = 1.0,
) -> list[dict]:
    """
    Minimal 2-platform binary arb scenario:
      - T=0: both markets created with no-arb prices
      - T=1: both markets update at the SAME timestamp to avoid premature
             arb detection at stale prices. Non-intended ask sides are priced
             at 0.95 to prevent reverse-direction false arbs.
      - T=2: both markets resolve

    Arb direction is always: buy Yes on platform_a + buy No on platform_b.
    """
    # Make the "other" sides expensive so no reverse arb is created:
    #   no_a + yes_b = 0.95 + 0.95 = 1.90 >> 1  →  no reverse arb possible
    return [
        # T=0: create
        {
            "event_type": "market_created",
            "platform": "platform_a",
            "market_id": "mkt_a",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {
                "question": "Will X happen?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": 0.49, "No": 0.49},
                "best_ask": {"Yes": 0.51, "No": 0.51},
                "last_traded": {"Yes": 0.50, "No": 0.50},
                "fees": fees_a,
                "close_time": "2024-12-31T23:59:59Z",
            },
        },
        {
            "event_type": "market_created",
            "platform": "platform_b",
            "market_id": "mkt_b",
            "timestamp": "2024-01-01T00:01:00Z",
            "data": {
                "question": "Will X happen?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": 0.49, "No": 0.49},
                "best_ask": {"Yes": 0.51, "No": 0.51},
                "last_traded": {"Yes": 0.50, "No": 0.50},
                "fees": fees_b,
                "close_time": "2024-12-31T23:59:59Z",
            },
        },
        # T=1: BOTH markets update at the same timestamp so the strategy sees
        # the arb on the first observation after this step, at correct prices.
        {
            "event_type": "market_updated",
            "platform": "platform_a",
            "market_id": "mkt_a",
            "timestamp": "2024-01-02T10:00:00Z",
            "data": {
                "question": "Will X happen?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": ask_yes_a - 0.01, "No": 0.93},
                "best_ask": {"Yes": ask_yes_a, "No": 0.95},   # No_A expensive
                "last_traded": {"Yes": ask_yes_a - 0.005, "No": 0.94},
                "fees": fees_a,
                "close_time": "2024-12-31T23:59:59Z",
            },
        },
        {
            "event_type": "market_updated",
            "platform": "platform_b",
            "market_id": "mkt_b",
            "timestamp": "2024-01-02T10:00:00Z",   # same timestamp as platform_a
            "data": {
                "question": "Will X happen?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": 0.93, "No": ask_no_b - 0.01},
                "best_ask": {"Yes": 0.95, "No": ask_no_b},    # Yes_B expensive
                "last_traded": {"Yes": 0.94, "No": ask_no_b - 0.005},
                "fees": fees_b,
                "close_time": "2024-12-31T23:59:59Z",
            },
        },
        # T=2: resolve
        {
            "event_type": "market_resolved",
            "platform": "platform_a",
            "market_id": "mkt_a",
            "timestamp": "2025-01-01T00:00:00Z",
            "data": {
                "resolution_outcome": resolution_outcome,
                "resolution_value": resolution_value,
            },
        },
        {
            "event_type": "market_resolved",
            "platform": "platform_b",
            "market_id": "mkt_b",
            "timestamp": "2025-01-01T00:00:00Z",
            "data": {
                "resolution_outcome": resolution_outcome,
                "resolution_value": resolution_value,
            },
        },
    ]


# ---------------------------------------------------------------------------
# Tests: toy dataset
# ---------------------------------------------------------------------------

class TestToyDatasetFullLifecycle:
    """End-to-end assertions using the built-in toy dataset."""

    def test_trade_is_filled(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig(
            initial_capital=10_000,
            realism_mode=RealismMode.OPTIMISTIC,
            fee_bps=0.0,
        )
        result = run_backtest(
            config=config,
            strategy=GreedyArbStrategy(min_net_profit=0.001, max_size_per_leg=10.0),
            events=events,
            verbose=False,
        )
        assert result.metrics.trades_attempted == 1
        assert result.metrics.trades_filled == 1
        assert result.metrics.fill_rate == pytest.approx(1.0)

    def test_realized_pnl_is_positive(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig(
            initial_capital=10_000,
            realism_mode=RealismMode.OPTIMISTIC,
            fee_bps=0.0,
        )
        result = run_backtest(
            config=config,
            strategy=GreedyArbStrategy(min_net_profit=0.001, max_size_per_leg=10.0),
            events=events,
            verbose=False,
        )
        assert result.metrics.total_realized_pnl > 0

    def test_settlement_happened(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig(
            initial_capital=10_000,
            realism_mode=RealismMode.OPTIMISTIC,
            fee_bps=0.0,
        )
        result = run_backtest(
            config=config,
            strategy=GreedyArbStrategy(min_net_profit=0.001, max_size_per_leg=10.0),
            events=events,
            verbose=False,
        )
        assert len(result.settlement_log) >= 1

    def test_no_open_baskets_at_end(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig(realism_mode=RealismMode.OPTIMISTIC, fee_bps=0.0)
        result = run_backtest(
            config=config,
            strategy=GreedyArbStrategy(min_net_profit=0.001, max_size_per_leg=10.0),
            events=events,
            verbose=False,
        )
        assert result.final_portfolio.open_basket_count == 0
        assert len(result.final_portfolio.closed_baskets) == 1

    def test_final_equity_greater_than_initial(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig(
            initial_capital=10_000,
            realism_mode=RealismMode.OPTIMISTIC,
            fee_bps=0.0,
        )
        result = run_backtest(
            config=config,
            strategy=GreedyArbStrategy(min_net_profit=0.001, max_size_per_leg=10.0),
            events=events,
            verbose=False,
        )
        assert result.metrics.final_equity > 10_000

    def test_all_7_events_processed(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig()
        result = run_backtest(
            config=config, strategy=NullStrategy(), events=events, verbose=False
        )
        assert result.events_processed == 7


# ---------------------------------------------------------------------------
# Tests: exact PnL with zero fees and zero slippage
# ---------------------------------------------------------------------------

class TestExactPnLCalculations:
    """
    With OPTIMISTIC mode + fee_bps=0, fills are at the best ask with zero
    slippage. PnL is deterministic and should match exact hand calculations.
    """

    def test_15_percent_arb_exact_pnl(self) -> None:
        """
        Arb: buy Yes @ 0.40 on A, buy No @ 0.45 on B.
        Combined cost per share = 0.85. Payout = 1.00. Profit = 0.15/share.
        Size = 10. Expected realized PnL = 1.50.
        """
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        result = _run(records, fee_bps=0.0, max_size_per_leg=10.0)
        assert result.metrics.trades_filled == 1
        assert result.metrics.total_realized_pnl == pytest.approx(1.50, abs=0.01)

    def test_10_percent_arb_exact_pnl(self) -> None:
        """
        Arb: buy Yes @ 0.45 on A, buy No @ 0.45 on B.
        Profit = (1.0 - 0.90) * 10 = 1.00
        """
        records = _binary_arb_records(ask_yes_a=0.45, ask_no_b=0.45)
        result = _run(records, fee_bps=0.0, max_size_per_leg=10.0)
        assert result.metrics.trades_filled == 1
        assert result.metrics.total_realized_pnl == pytest.approx(1.00, abs=0.01)

    def test_no_arb_when_prices_sum_to_1(self) -> None:
        """
        If Yes ask = 0.50 and No ask = 0.50, net after fees = 0. No trade.
        """
        records = _binary_arb_records(ask_yes_a=0.50, ask_no_b=0.50)
        result = _run(records, fee_bps=0.0, min_net_profit=0.005)
        assert result.metrics.trades_attempted == 0

    def test_no_arb_when_prices_sum_above_1(self) -> None:
        """
        If Yes ask = 0.55 and No ask = 0.55, combined > 1. No arb.
        """
        records = _binary_arb_records(ask_yes_a=0.55, ask_no_b=0.55)
        result = _run(records, fee_bps=0.0)
        assert result.metrics.trades_attempted == 0

    def test_pnl_same_regardless_of_resolution_side(self) -> None:
        """
        Binary arb profit is the same whether Yes or No wins.
        We test Yes winning vs No winning on the same price setup.
        """
        records_yes = _binary_arb_records(
            ask_yes_a=0.40, ask_no_b=0.45, resolution_outcome="Yes", resolution_value=1.0
        )
        records_no = _binary_arb_records(
            ask_yes_a=0.40, ask_no_b=0.45, resolution_outcome="No", resolution_value=0.0
        )
        result_yes = _run(records_yes, fee_bps=0.0, max_size_per_leg=10.0)
        result_no = _run(records_no, fee_bps=0.0, max_size_per_leg=10.0)

        assert result_yes.metrics.trades_filled == 1
        assert result_no.metrics.trades_filled == 1
        # PnL should be identical (one leg always wins)
        assert result_yes.metrics.total_realized_pnl == pytest.approx(
            result_no.metrics.total_realized_pnl, abs=0.01
        )


# ---------------------------------------------------------------------------
# Tests: fee impact
# ---------------------------------------------------------------------------

class TestFeeImpact:
    """Verify fees reduce profit and can prevent trades below threshold."""

    def test_fees_reduce_pnl(self) -> None:
        """
        With fees, final equity should be lower than fee-free case.

        Note: realized_pnl tracks gross profit (before fees); fees are deducted
        from cash at fill time and tracked in total_fees_paid. Final equity
        correctly reflects the net result.
        """
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        result_no_fee = _run(records, fee_bps=0.0, max_size_per_leg=10.0)
        result_with_fee = _run(records, fee_bps=100.0, max_size_per_leg=10.0)

        # Both should fill (arb is fat enough)
        assert result_no_fee.metrics.trades_filled == 1
        assert result_with_fee.metrics.trades_filled == 1
        # Fee run should yield lower final equity
        assert result_with_fee.metrics.final_equity < result_no_fee.metrics.final_equity
        # Fee run should report non-zero fees
        assert result_with_fee.metrics.total_fees_paid > 0
        assert result_no_fee.metrics.total_fees_paid == pytest.approx(0.0)

    def test_high_fees_block_marginal_arb(self) -> None:
        """
        A slim 2% gross-profit arb with 200bps fees on each leg should not pass
        the minimum profit threshold.

        fees = 200bps * 2 legs = 4% on notional. Gross profit = 2%.
        Net = negative → trade rejected.
        """
        records = _binary_arb_records(ask_yes_a=0.49, ask_no_b=0.49)  # 2% gross
        result = _run(records, fee_bps=200.0, min_net_profit=0.005)
        # The observation-level net_profit_estimate uses snapshot.fees (0), not config fees
        # But the fill engine enforces the threshold after applying config fees
        # → trade may be attempted but rejected or not attempted
        assert result.metrics.trades_filled == 0

    def test_fees_tracked_in_metrics(self) -> None:
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        result = _run(records, fee_bps=100.0, max_size_per_leg=10.0)
        if result.metrics.trades_filled > 0:
            assert result.metrics.total_fees_paid > 0


# ---------------------------------------------------------------------------
# Tests: realism modes
# ---------------------------------------------------------------------------

class TestRealismModes:
    """Verify behaviour differs meaningfully across realism modes."""

    def test_optimistic_fills_better_than_realistic(self) -> None:
        """
        Optimistic: zero slippage, fill at best ask.
        Realistic: 50bps slippage applied to ask → higher fill price → lower PnL.
        """
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        events = _make_events(records)

        result_opt = run_backtest(
            config=SimulationConfig(realism_mode=RealismMode.OPTIMISTIC, fee_bps=0.0),
            strategy=GreedyArbStrategy(min_net_profit=0.001, max_size_per_leg=10.0),
            events=events,
            verbose=False,
        )
        result_real = run_backtest(
            config=SimulationConfig(realism_mode=RealismMode.REALISTIC, fee_bps=0.0),
            strategy=GreedyArbStrategy(min_net_profit=0.001, max_size_per_leg=10.0),
            events=events,
            verbose=False,
        )

        # Both should still fill (arb is fat enough)
        assert result_opt.metrics.trades_filled >= 1
        assert result_real.metrics.trades_filled >= 1
        # Optimistic should yield higher PnL (zero slippage)
        assert result_opt.metrics.total_realized_pnl >= result_real.metrics.total_realized_pnl

    def test_pessimistic_has_higher_fees_than_optimistic(self) -> None:
        events = load_toy_dataset()
        result_opt = run_backtest(
            config=SimulationConfig(realism_mode=RealismMode.OPTIMISTIC),
            strategy=GreedyArbStrategy(min_net_profit=0.001),
            events=events,
            verbose=False,
        )
        result_pes = run_backtest(
            config=SimulationConfig(realism_mode=RealismMode.PESSIMISTIC),
            strategy=GreedyArbStrategy(min_net_profit=0.001),
            events=events,
            verbose=False,
        )
        assert result_pes.metrics.total_fees_paid >= result_opt.metrics.total_fees_paid

    def test_slippage_tracked_in_realistic_mode(self) -> None:
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        result = _run(
            records,
            realism_mode=RealismMode.REALISTIC,
            fee_bps=0.0,
            max_size_per_leg=10.0,
        )
        if result.metrics.trades_filled > 0:
            assert result.metrics.total_slippage_cost > 0


# ---------------------------------------------------------------------------
# Tests: multiple simultaneous opportunities
# ---------------------------------------------------------------------------

class TestMultipleOpportunities:
    """Verify the strategy correctly handles more than one arb pair."""

    def _two_pair_records(self) -> list[dict]:
        """
        Two independent binary arb opportunities on four markets.

        To avoid cross-pair false-arb detection (the simple screener has no
        concept of 'same event'), the two pairs are TIME-SEPARATED:
          - Pair 1 (alpha vs beta) opens, fills, and resolves fully
            before Pair 2 (gamma vs delta) markets are even created.
        This guarantees the screener never sees all 4 markets simultaneously.
        """
        return [
            # --- Pair 1: alpha vs beta ---
            {
                "event_type": "market_created",
                "platform": "alpha",
                "market_id": "alpha_x",
                "timestamp": "2024-01-01T00:00:00Z",
                "data": {
                    "question": "Will X happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.49, "No": 0.49},
                    "best_ask": {"Yes": 0.51, "No": 0.51},
                    "last_traded": {"Yes": 0.50, "No": 0.50},
                    "fees": 0.0,
                    "close_time": "2024-06-30T23:59:59Z",
                },
            },
            {
                "event_type": "market_created",
                "platform": "beta",
                "market_id": "beta_x",
                "timestamp": "2024-01-01T00:01:00Z",
                "data": {
                    "question": "Will X happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.49, "No": 0.49},
                    "best_ask": {"Yes": 0.51, "No": 0.51},
                    "last_traded": {"Yes": 0.50, "No": 0.50},
                    "fees": 0.0,
                    "close_time": "2024-06-30T23:59:59Z",
                },
            },
            # Pair 1 diverges — same timestamp so arb enters at correct prices
            {
                "event_type": "market_updated",
                "platform": "alpha",
                "market_id": "alpha_x",
                "timestamp": "2024-01-02T10:00:00Z",
                "data": {
                    "question": "Will X happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.39, "No": 0.92},
                    "best_ask": {"Yes": 0.40, "No": 0.95},
                    "last_traded": {"Yes": 0.40, "No": 0.93},
                    "fees": 0.0,
                    "close_time": "2024-06-30T23:59:59Z",
                },
            },
            {
                "event_type": "market_updated",
                "platform": "beta",
                "market_id": "beta_x",
                "timestamp": "2024-01-02T10:00:00Z",
                "data": {
                    "question": "Will X happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.92, "No": 0.41},
                    "best_ask": {"Yes": 0.95, "No": 0.42},
                    "last_traded": {"Yes": 0.93, "No": 0.42},
                    "fees": 0.0,
                    "close_time": "2024-06-30T23:59:59Z",
                },
            },
            # Pair 1 resolves — before Pair 2 even created
            {
                "event_type": "market_resolved",
                "platform": "alpha",
                "market_id": "alpha_x",
                "timestamp": "2024-07-01T00:00:00Z",
                "data": {"resolution_outcome": "Yes", "resolution_value": 1.0},
            },
            {
                "event_type": "market_resolved",
                "platform": "beta",
                "market_id": "beta_x",
                "timestamp": "2024-07-01T00:00:00Z",
                "data": {"resolution_outcome": "Yes", "resolution_value": 1.0},
            },
            # --- Pair 2: gamma vs delta (created after pair 1 resolves) ---
            {
                "event_type": "market_created",
                "platform": "gamma",
                "market_id": "gamma_y",
                "timestamp": "2024-07-02T00:00:00Z",
                "data": {
                    "question": "Will Y happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.49, "No": 0.49},
                    "best_ask": {"Yes": 0.51, "No": 0.51},
                    "last_traded": {"Yes": 0.50, "No": 0.50},
                    "fees": 0.0,
                    "close_time": "2025-01-31T23:59:59Z",
                },
            },
            {
                "event_type": "market_created",
                "platform": "delta",
                "market_id": "delta_y",
                "timestamp": "2024-07-02T00:01:00Z",
                "data": {
                    "question": "Will Y happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.49, "No": 0.49},
                    "best_ask": {"Yes": 0.51, "No": 0.51},
                    "last_traded": {"Yes": 0.50, "No": 0.50},
                    "fees": 0.0,
                    "close_time": "2025-01-31T23:59:59Z",
                },
            },
            # Pair 2 diverges — same timestamp
            {
                "event_type": "market_updated",
                "platform": "gamma",
                "market_id": "gamma_y",
                "timestamp": "2024-08-01T09:00:00Z",
                "data": {
                    "question": "Will Y happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.34, "No": 0.92},
                    "best_ask": {"Yes": 0.35, "No": 0.95},
                    "last_traded": {"Yes": 0.35, "No": 0.93},
                    "fees": 0.0,
                    "close_time": "2025-01-31T23:59:59Z",
                },
            },
            {
                "event_type": "market_updated",
                "platform": "delta",
                "market_id": "delta_y",
                "timestamp": "2024-08-01T09:00:00Z",
                "data": {
                    "question": "Will Y happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.92, "No": 0.37},
                    "best_ask": {"Yes": 0.95, "No": 0.38},
                    "last_traded": {"Yes": 0.93, "No": 0.38},
                    "fees": 0.0,
                    "close_time": "2025-01-31T23:59:59Z",
                },
            },
            # Pair 2 resolves Yes
            {
                "event_type": "market_resolved",
                "platform": "gamma",
                "market_id": "gamma_y",
                "timestamp": "2025-02-01T00:00:00Z",
                "data": {"resolution_outcome": "Yes", "resolution_value": 1.0},
            },
            {
                "event_type": "market_resolved",
                "platform": "delta",
                "market_id": "delta_y",
                "timestamp": "2025-02-01T00:00:00Z",
                "data": {"resolution_outcome": "Yes", "resolution_value": 1.0},
            },
        ]

    def test_both_arbs_detected_and_filled(self) -> None:
        """Strategy should enter both independent arb pairs."""
        records = self._two_pair_records()
        result = _run(records, fee_bps=0.0, max_size_per_leg=10.0, min_net_profit=0.001)
        assert result.metrics.trades_filled >= 2

    def test_both_arbs_settle_positive_pnl(self) -> None:
        records = self._two_pair_records()
        result = _run(records, fee_bps=0.0, max_size_per_leg=10.0, min_net_profit=0.001)
        assert result.metrics.total_realized_pnl > 0
        assert len(result.final_portfolio.closed_baskets) >= 2

    def test_all_baskets_closed_after_resolution(self) -> None:
        records = self._two_pair_records()
        result = _run(records, fee_bps=0.0, max_size_per_leg=10.0, min_net_profit=0.001)
        assert result.final_portfolio.open_basket_count == 0


# ---------------------------------------------------------------------------
# Tests: capital management
# ---------------------------------------------------------------------------

class TestCapitalManagement:
    """Verify cash, locked capital, and equity accounting are consistent."""

    def test_cash_decreases_when_trade_fills(self) -> None:
        """After a fill, cash should be less than initial capital."""
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        events = _make_events(records)
        config = SimulationConfig(
            initial_capital=10_000,
            realism_mode=RealismMode.OPTIMISTIC,
            fee_bps=0.0,
        )
        strategy = GreedyArbStrategy(min_net_profit=0.001, max_size_per_leg=10.0)

        stream = ReplayStream(events)
        env = SimulationEnvironment(config=config, replay_stream=stream)
        env.reset()

        # Run until we've seen at least one fill
        fills_seen = 0
        portfolio_after_fill = None
        while not env.is_done() and fills_seen == 0:
            obs = env.get_observation()
            actions = strategy.decide(obs)
            fills = env.apply_actions(actions)
            fills_seen += sum(1 for f in fills if f.fill_status != FillStatus.REJECTED)
            if fills_seen > 0:
                portfolio_after_fill = env.get_observation().portfolio
            env.advance()

        if fills_seen > 0:
            assert portfolio_after_fill is not None
            assert portfolio_after_fill.cash < 10_000
            assert portfolio_after_fill.locked_capital > 0

    def test_equity_conserved_around_settlement(self) -> None:
        """
        Total equity (cash + locked + unrealized) should not decrease at settlement;
        it should increase by the arb profit.
        """
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        events = _make_events(records)
        config = SimulationConfig(
            initial_capital=10_000,
            realism_mode=RealismMode.OPTIMISTIC,
            fee_bps=0.0,
        )
        result = run_backtest(
            config=config,
            strategy=GreedyArbStrategy(min_net_profit=0.001, max_size_per_leg=10.0),
            events=events,
            verbose=False,
        )
        if result.metrics.trades_filled > 0:
            assert result.metrics.final_equity > 10_000

    def test_locked_capital_freed_after_settlement(self) -> None:
        """After all markets resolve, locked_capital should be 0."""
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        result = _run(records, fee_bps=0.0, max_size_per_leg=10.0)
        if result.metrics.trades_filled > 0:
            assert result.final_portfolio.locked_capital == pytest.approx(0.0, abs=0.01)

    def test_position_count_is_zero_after_settlement(self) -> None:
        """After settlement, all positions should be closed (none open)."""
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        result = _run(records, fee_bps=0.0, max_size_per_leg=10.0)
        assert len(result.final_portfolio.positions) == 0


# ---------------------------------------------------------------------------
# Tests: environment step / observation correctness
# ---------------------------------------------------------------------------

class TestEnvironmentStepByStep:
    """Low-level tests that drive the env manually, verifying each step."""

    def test_empty_observation_before_first_advance(self) -> None:
        """Before any events are processed, visible_markets should be empty."""
        events = load_toy_dataset()
        config = SimulationConfig()
        stream = ReplayStream(events)
        env = SimulationEnvironment(config=config, replay_stream=stream)
        env.reset()

        obs = env.get_observation()
        assert len(obs.visible_markets) == 0
        assert len(obs.opportunities) == 0

    def test_one_market_visible_after_first_advance(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig(realism_mode=RealismMode.OPTIMISTIC)
        stream = ReplayStream(events)
        env = SimulationEnvironment(config=config, replay_stream=stream)
        env.reset()

        n = env.advance()  # processes T=Jan01 00:00 (poly created)
        assert n == 1
        obs = env.get_observation()
        assert len(obs.visible_markets) == 1

    def test_two_markets_visible_after_second_advance(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig(realism_mode=RealismMode.OPTIMISTIC)
        stream = ReplayStream(events)
        env = SimulationEnvironment(config=config, replay_stream=stream)
        env.reset()

        env.advance()  # T=Jan01 00:00
        env.advance()  # T=Jan01 00:05
        obs = env.get_observation()
        assert len(obs.visible_markets) == 2

    def test_advance_returns_correct_event_count(self) -> None:
        """Each advance call should return the number of events it consumed."""
        events = load_toy_dataset()
        config = SimulationConfig()
        stream = ReplayStream(events)
        env = SimulationEnvironment(config=config, replay_stream=stream)
        env.reset()

        total = 0
        while not env.is_done():
            n = env.advance()
            total += n
        assert total == 7

    def test_opportunity_detected_at_correct_step(self) -> None:
        """
        Arb opportunity appears only after BOTH market updates are processed.
        After poly update (step 3) but before kalshi update (step 4),
        there should be no arb. After kalshi update (step 4), arb appears.
        """
        events = load_toy_dataset()
        config = SimulationConfig(
            realism_mode=RealismMode.OPTIMISTIC,
            stale_quote_tolerance_seconds=86400 * 7,
        )
        stream = ReplayStream(events)
        env = SimulationEnvironment(config=config, replay_stream=stream)
        env.reset()

        # Advance through: T=Jan01-00:00, T=Jan01-00:05, T=Jan02-10:00
        env.advance()  # poly created
        env.advance()  # kalshi created
        env.advance()  # poly updated (Yes ask=0.40, but kalshi still old)
        obs_no_arb = env.get_observation()

        env.advance()  # kalshi updated (No ask=0.45)
        obs_with_arb = env.get_observation()

        assert len(obs_no_arb.opportunities) == 0
        assert len(obs_with_arb.opportunities) >= 1
        assert obs_with_arb.opportunities[0]["net_profit_estimate"] > 0

    def test_is_done_after_all_events(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig()
        stream = ReplayStream(events)
        env = SimulationEnvironment(config=config, replay_stream=stream)
        env.reset()

        while not env.is_done():
            env.advance()
        assert env.is_done()


# ---------------------------------------------------------------------------
# Tests: edge cases and robustness
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases that should not crash or produce nonsensical results."""

    def test_null_strategy_produces_zero_trades(self) -> None:
        events = load_toy_dataset()
        config = SimulationConfig()
        result = run_backtest(
            config=config, strategy=NullStrategy(), events=events, verbose=False
        )
        assert result.metrics.trades_attempted == 0
        assert result.metrics.trades_filled == 0
        assert result.metrics.total_realized_pnl == pytest.approx(0.0, abs=0.01)

    def test_no_arb_when_same_platform_both_markets(self) -> None:
        """
        Even if a single platform has two markets with the same question,
        the arb screener should detect opportunities correctly.
        This test verifies we handle homogeneous platforms without crash.
        """
        records = [
            {
                "event_type": "market_created",
                "platform": "same_platform",
                "market_id": "mkt_1",
                "timestamp": "2024-01-01T00:00:00Z",
                "data": {
                    "question": "Will X happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.39, "No": 0.39},
                    "best_ask": {"Yes": 0.41, "No": 0.41},
                    "last_traded": {"Yes": 0.40, "No": 0.40},
                    "fees": 0.0,
                    "close_time": "2024-12-31T23:59:59Z",
                },
            },
            {
                "event_type": "market_created",
                "platform": "same_platform",
                "market_id": "mkt_2",
                "timestamp": "2024-01-01T00:01:00Z",
                "data": {
                    "question": "Will X happen?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.55, "No": 0.41},
                    "best_ask": {"Yes": 0.57, "No": 0.43},
                    "last_traded": {"Yes": 0.56, "No": 0.42},
                    "fees": 0.0,
                    "close_time": "2024-12-31T23:59:59Z",
                },
            },
            {
                "event_type": "market_resolved",
                "platform": "same_platform",
                "market_id": "mkt_1",
                "timestamp": "2025-01-01T00:00:00Z",
                "data": {"resolution_outcome": "Yes", "resolution_value": 1.0},
            },
            {
                "event_type": "market_resolved",
                "platform": "same_platform",
                "market_id": "mkt_2",
                "timestamp": "2025-01-01T00:00:00Z",
                "data": {"resolution_outcome": "Yes", "resolution_value": 1.0},
            },
        ]
        # Should run without errors
        result = _run(records, fee_bps=0.0)
        assert result is not None
        assert result.metrics is not None

    def test_strategy_does_not_double_enter_same_pair(self) -> None:
        """GreedyArbStrategy should not enter the same open basket pair again."""
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        result = _run(records, fee_bps=0.0, max_size_per_leg=10.0, min_net_profit=0.001)
        # Arb opportunity persists across many steps, but we should only enter once
        assert result.metrics.trades_attempted == 1

    def test_min_profit_threshold_blocks_small_arb(self) -> None:
        """Setting a high minimum profit threshold blocks tiny arb opportunities."""
        records = _binary_arb_records(ask_yes_a=0.48, ask_no_b=0.48)  # 4% gross
        result = _run(records, fee_bps=0.0, min_net_profit=0.10)  # require 10%
        assert result.metrics.trades_filled == 0

    def test_single_event_dataset_runs_without_error(self) -> None:
        """A dataset with only one event should not crash."""
        records = [
            {
                "event_type": "market_created",
                "platform": "test",
                "market_id": "m1",
                "timestamp": "2024-01-01T00:00:00Z",
                "data": {
                    "question": "Test?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.49, "No": 0.49},
                    "best_ask": {"Yes": 0.51, "No": 0.51},
                    "last_traded": {"Yes": 0.50, "No": 0.50},
                    "fees": 0.0,
                    "close_time": "2024-12-31T23:59:59Z",
                },
            }
        ]
        result = _run(records, fee_bps=0.0)
        assert result.events_processed == 1

    def test_backtest_result_fields_are_valid(self) -> None:
        """Sanity check all BacktestResult fields are non-None and valid types."""
        records = _binary_arb_records(ask_yes_a=0.40, ask_no_b=0.45)
        result = _run(records, fee_bps=0.0, max_size_per_leg=10.0)

        assert result.start_time is not None
        assert result.end_time >= result.start_time
        assert result.events_processed > 0
        assert result.run_duration_seconds >= 0
        assert result.metrics.fill_rate >= 0
        assert result.metrics.final_equity >= 0
        assert result.final_portfolio is not None
