"""Spread computation utilities for Phase 4.

The spread is the difference between the YES price on one platform and
the implied YES price on the other.  A positive spread means we can buy
cheap on one side and sell dear on the other.
"""

from __future__ import annotations

from algorithm.Phase_4.models import Direction, MatchedPair


def compute_spread(pair: MatchedPair) -> tuple[float, Direction]:
    """Return (raw_spread, direction).

    Convention:
        spread = price_high − price_low   (always ≥ 0)
        direction tells you which leg is cheap.

    A simple arbitrage exists when two platforms price the *same* binary
    event differently.  If Polymarket YES = 0.70 and Kalshi YES = 0.63,
    the spread is 0.07 and the direction is BUY_B_SELL_A.
    """
    price_a = pair.market_a.yes_price
    price_b = pair.market_b.yes_price

    spread = price_a - price_b  # positive → A is more expensive

    if spread >= 0:
        return round(abs(spread), 6), Direction.BUY_B_SELL_A
    else:
        return round(abs(spread), 6), Direction.BUY_A_SELL_B


def two_sided_spread(pair: MatchedPair) -> float:
    """Check the *guaranteed* two-sided arbitrage.

    If you buy YES on the cheap platform and NO on the expensive platform
    (buy NO = sell YES there), you lock in profit when combined cost < 1.00.

    guaranteed_profit = 1 - (cheap_yes + expensive_no)

    This is always ≤ the raw spread but represents risk-free profit.
    """
    price_a = pair.market_a.yes_price
    price_b = pair.market_b.yes_price

    # Case 1: buy YES on B (cheap), buy NO on A (expensive)
    cost_1 = price_b + pair.market_a.no_price
    # Case 2: buy YES on A, buy NO on B
    cost_2 = price_a + pair.market_b.no_price

    best_cost = min(cost_1, cost_2)
    guaranteed = 1.0 - best_cost  # positive = free money
    return round(max(guaranteed, 0.0), 6)
