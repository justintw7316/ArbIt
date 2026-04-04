"""
Report generation.

Produces structured summary reports from BacktestResult.
Supports:
  - dict/JSON export
  - plaintext console summary
"""

from __future__ import annotations

import json
from datetime import datetime

from simulation.models import BacktestResult


def summary_dict(result: BacktestResult) -> dict:
    """Return a flat dict suitable for JSON export or DataFrame construction."""
    m = result.metrics
    return {
        "start_time": result.start_time.isoformat(),
        "end_time": result.end_time.isoformat(),
        "run_duration_s": round(result.run_duration_seconds, 2),
        "events_processed": result.events_processed,
        # PnL
        "realized_pnl": round(m.total_realized_pnl, 4),
        "unrealized_pnl": round(m.total_unrealized_pnl, 4),
        "fees_paid": round(m.total_fees_paid, 4),
        "slippage_cost": round(m.total_slippage_cost, 4),
        "final_equity": round(m.final_equity, 4),
        # Trade stats
        "trades_attempted": m.trades_attempted,
        "trades_filled": m.trades_filled,
        "partial_fills": m.partial_fills,
        "fill_rate": round(m.fill_rate, 4),
        "win_rate": round(m.win_rate, 4),
        "avg_profit_per_trade": round(m.avg_profit_per_trade, 6),
        "avg_holding_hours": round(m.avg_holding_period_hours, 2),
        # Capital
        "max_locked_capital": round(m.max_locked_capital, 4),
        # Risk
        "sharpe_ratio": round(m.sharpe_ratio, 4) if m.sharpe_ratio is not None else None,
        "max_drawdown": round(m.max_drawdown, 4),
        # Breakdown
        "profit_by_arb_type": {k: round(v, 4) for k, v in m.profit_by_arb_type.items()},
        # Portfolio
        "open_baskets": result.final_portfolio.open_basket_count,
        "closed_baskets": len(result.final_portfolio.closed_baskets),
    }


def print_summary(result: BacktestResult) -> None:
    """Print a human-readable backtest summary to stdout."""
    d = summary_dict(result)
    width = 56

    def line(label: str, value: object) -> str:
        return f"  {label:<32} {value!s:>20}"

    print("=" * width)
    print(f"  BACKTEST SUMMARY")
    print(f"  {d['start_time'][:10]} → {d['end_time'][:10]}")
    print("=" * width)
    print(line("Events processed:", d["events_processed"]))
    print(line("Run duration (s):", d["run_duration_s"]))
    print("-" * width)
    print(line("Realized PnL:", f"${d['realized_pnl']:+.4f}"))
    print(line("Unrealized PnL:", f"${d['unrealized_pnl']:+.4f}"))
    print(line("Fees paid:", f"${d['fees_paid']:.4f}"))
    print(line("Slippage cost:", f"${d['slippage_cost']:.4f}"))
    print(line("Final equity:", f"${d['final_equity']:.4f}"))
    print("-" * width)
    print(line("Trades attempted:", d["trades_attempted"]))
    print(line("Trades filled:", d["trades_filled"]))
    print(line("Partial fills:", d["partial_fills"]))
    print(line("Fill rate:", f"{d['fill_rate']:.1%}"))
    print(line("Win rate:", f"{d['win_rate']:.1%}"))
    print(line("Avg profit/trade:", f"${d['avg_profit_per_trade']:.4f}"))
    print(line("Avg holding period:", f"{d['avg_holding_hours']:.1f}h"))
    print("-" * width)
    print(line("Max locked capital:", f"${d['max_locked_capital']:.4f}"))
    sharpe = d["sharpe_ratio"]
    print(line("Sharpe ratio:", f"{sharpe:.3f}" if sharpe is not None else "N/A"))
    print(line("Max drawdown:", f"{d['max_drawdown']:.2%}"))
    print("-" * width)
    if d["profit_by_arb_type"]:
        print("  Profit by arb type:")
        for k, v in d["profit_by_arb_type"].items():
            print(line(f"    {k}:", f"${v:+.4f}"))
    print(line("Open baskets:", d["open_baskets"]))
    print(line("Closed baskets:", d["closed_baskets"]))
    print("=" * width)


def to_json(result: BacktestResult, indent: int = 2) -> str:
    """Serialize summary to JSON string."""
    return json.dumps(summary_dict(result), indent=indent, default=str)
