"""
Backtest metrics computation.

Computes all summary statistics from portfolio state + logs.
All calculations are pure functions — no side effects.
"""

from __future__ import annotations

import math
from datetime import timedelta

from simulation.models import (
    BacktestMetrics,
    FillResult,
    FillStatus,
    PortfolioState,
    SettlementResult,
)


def compute_metrics(
    initial_capital: float,
    portfolio: PortfolioState,
    fill_log: list[FillResult],
    settlement_log: list[SettlementResult],
) -> BacktestMetrics:
    """Compute all backtest metrics from final portfolio state and logs."""

    # ------------------------------------------------------------------
    # PnL
    # ------------------------------------------------------------------
    total_realized = portfolio.realized_pnl
    total_unrealized = portfolio.unrealized_pnl
    total_fees = portfolio.total_fees_paid

    total_slippage = sum(f.total_slippage_cost for f in fill_log)

    # ------------------------------------------------------------------
    # Fill statistics
    # ------------------------------------------------------------------
    attempted = len(fill_log)
    filled = sum(1 for f in fill_log if f.fill_status == FillStatus.FILLED)
    partial = sum(1 for f in fill_log if f.fill_status == FillStatus.PARTIAL)
    fill_rate = filled / attempted if attempted > 0 else 0.0

    # ------------------------------------------------------------------
    # Trade economics
    # ------------------------------------------------------------------
    profitable_trades = [
        b for b in portfolio.closed_baskets
        if (b.realized_pnl or 0.0) > 0
    ]
    win_rate = (
        len(profitable_trades) / len(portfolio.closed_baskets)
        if portfolio.closed_baskets
        else 0.0
    )

    avg_profit = (
        total_realized / len(portfolio.closed_baskets)
        if portfolio.closed_baskets
        else 0.0
    )

    # ------------------------------------------------------------------
    # Capital usage
    # ------------------------------------------------------------------
    max_locked = max(
        (f.locked_capital for f in fill_log if f.fill_status == FillStatus.FILLED),
        default=0.0,
    )

    # ------------------------------------------------------------------
    # Holding period
    # ------------------------------------------------------------------
    holding_hours: list[float] = []
    for basket in portfolio.closed_baskets:
        if basket.open_time and basket.close_time:
            delta = basket.close_time - basket.open_time
            holding_hours.append(delta.total_seconds() / 3600)
    avg_holding = sum(holding_hours) / len(holding_hours) if holding_hours else 0.0

    # ------------------------------------------------------------------
    # Profit by arb type
    # ------------------------------------------------------------------
    by_type: dict[str, float] = {}
    for b in portfolio.closed_baskets:
        if b.realized_pnl is not None:
            by_type[b.arb_type] = by_type.get(b.arb_type, 0.0) + b.realized_pnl

    # ------------------------------------------------------------------
    # Final equity
    # ------------------------------------------------------------------
    final_equity = portfolio.total_equity

    # ------------------------------------------------------------------
    # Max drawdown (from equity curve, if available)
    # ------------------------------------------------------------------
    max_drawdown = 0.0
    equity_peak = initial_capital
    # Approximate from closed basket PnL series
    running = initial_capital
    for b in portfolio.closed_baskets:
        running += b.realized_pnl or 0.0
        equity_peak = max(equity_peak, running)
        dd = (equity_peak - running) / equity_peak if equity_peak > 0 else 0.0
        max_drawdown = max(max_drawdown, dd)

    # ------------------------------------------------------------------
    # Sharpe ratio (simplified, uses realized trade returns)
    # ------------------------------------------------------------------
    returns = [
        (b.realized_pnl or 0.0) / b.locked_capital
        for b in portfolio.closed_baskets
        if b.locked_capital > 0
    ]
    sharpe: float | None = None
    if len(returns) >= 3:
        mean_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / len(returns))
        if std_r > 0:
            sharpe = mean_r / std_r

    return BacktestMetrics(
        total_realized_pnl=total_realized,
        total_unrealized_pnl=total_unrealized,
        total_fees_paid=total_fees,
        total_slippage_cost=total_slippage,
        equity_curve=[],   # populated by env if equity sampling is enabled
        opportunities_detected=0,  # set by runner
        trades_attempted=attempted,
        trades_filled=filled,
        partial_fills=partial,
        fill_rate=fill_rate,
        avg_profit_per_trade=avg_profit,
        max_locked_capital=max_locked,
        avg_holding_period_hours=avg_holding,
        profit_by_arb_type=by_type,
        final_equity=final_equity,
        sharpe_ratio=sharpe,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
    )
