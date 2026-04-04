"""
Chart data generation.

Produces chart-ready data structures (dicts/lists) without any matplotlib
or plotting library dependency. The caller can render these with any library.

Each function returns a dict with keys:
  title, x_label, y_label, series: list[{name, x, y}]
"""

from __future__ import annotations

from simulation.models import BacktestResult, FillStatus


def equity_curve_data(result: BacktestResult, initial_capital: float) -> dict:
    """
    Equity curve: cumulative portfolio value over time.
    Uses closed basket PnL to reconstruct the curve chronologically.
    """
    events: list[tuple[str, float]] = []
    running = initial_capital

    # Start point
    events.append((result.start_time.isoformat(), initial_capital))

    # Add each basket close
    closed = sorted(
        [b for b in result.final_portfolio.closed_baskets if b.close_time is not None],
        key=lambda b: b.close_time,  # type: ignore[arg-type]
    )
    for basket in closed:
        running += basket.realized_pnl or 0.0
        events.append((basket.close_time.isoformat(), round(running, 4)))  # type: ignore[union-attr]

    # End point
    events.append((result.end_time.isoformat(), round(result.metrics.final_equity, 4)))

    xs = [e[0] for e in events]
    ys = [e[1] for e in events]

    return {
        "title": "Portfolio Equity Curve",
        "x_label": "Time",
        "y_label": "Equity ($)",
        "series": [{"name": "equity", "x": xs, "y": ys}],
    }


def pnl_per_basket_data(result: BacktestResult) -> dict:
    """Bar chart: realized PnL per closed basket."""
    closed = sorted(
        result.final_portfolio.closed_baskets,
        key=lambda b: b.close_time or result.end_time,
    )
    xs = [b.basket_id[:8] for b in closed]
    ys = [round(b.realized_pnl or 0.0, 4) for b in closed]

    return {
        "title": "Realized PnL per Basket",
        "x_label": "Basket ID",
        "y_label": "Realized PnL ($)",
        "series": [{"name": "pnl", "x": xs, "y": ys}],
    }


def fill_status_distribution_data(result: BacktestResult) -> dict:
    """Pie/bar: distribution of fill statuses."""
    counts: dict[str, int] = {}
    for fill in result.trade_log:
        key = fill.fill_status.value
        counts[key] = counts.get(key, 0) + 1

    return {
        "title": "Fill Status Distribution",
        "x_label": "Status",
        "y_label": "Count",
        "series": [
            {"name": "fills", "x": list(counts.keys()), "y": list(counts.values())}
        ],
    }


def profit_by_arb_type_data(result: BacktestResult) -> dict:
    """Bar: realized profit by arbitrage type."""
    data = result.metrics.profit_by_arb_type
    return {
        "title": "Profit by Arb Type",
        "x_label": "Arb Type",
        "y_label": "Realized PnL ($)",
        "series": [
            {"name": "pnl", "x": list(data.keys()), "y": [round(v, 4) for v in data.values()]}
        ],
    }


def holding_period_histogram_data(result: BacktestResult) -> dict:
    """Histogram: holding periods in hours."""
    hours: list[float] = []
    for b in result.final_portfolio.closed_baskets:
        if b.open_time and b.close_time:
            delta = (b.close_time - b.open_time).total_seconds() / 3600
            hours.append(round(delta, 2))

    return {
        "title": "Holding Period Distribution",
        "x_label": "Hours",
        "y_label": "Count",
        "series": [{"name": "holding_hours", "x": list(range(len(hours))), "y": hours}],
    }


def cumulative_fees_data(result: BacktestResult) -> dict:
    """Line: cumulative fees paid over time."""
    fills = sorted(result.trade_log, key=lambda f: f.fill_time)
    cumulative = 0.0
    xs: list[str] = []
    ys: list[float] = []
    for fill in fills:
        cumulative += fill.total_fees
        xs.append(fill.fill_time.isoformat())
        ys.append(round(cumulative, 6))

    return {
        "title": "Cumulative Fees Paid",
        "x_label": "Time",
        "y_label": "Cumulative Fees ($)",
        "series": [{"name": "fees", "x": xs, "y": ys}],
    }


def all_charts(result: BacktestResult, initial_capital: float) -> dict[str, dict]:
    """Return all chart data in a single dict."""
    return {
        "equity_curve": equity_curve_data(result, initial_capital),
        "pnl_per_basket": pnl_per_basket_data(result),
        "fill_status": fill_status_distribution_data(result),
        "profit_by_type": profit_by_arb_type_data(result),
        "holding_periods": holding_period_histogram_data(result),
        "cumulative_fees": cumulative_fees_data(result),
    }
