"""
Observation builder.

Constructs the Observation object that is handed to the strategy at each
timestep. This is the only interface between the environment and the strategy
— it must never contain future data.
"""

from __future__ import annotations

from datetime import datetime

from simulation.models import (
    ArbBasket,
    FillResult,
    MarketSnapshot,
    MarketStatus,
    Observation,
    PortfolioState,
    SettlementResult,
)


class ObservationBuilder:
    """Builds Observation objects from raw environment state components."""

    def build(
        self,
        sim_time: datetime,
        market_states: dict,  # market_key -> MarketState
        portfolio: PortfolioState,
        recent_fills: list[FillResult],
        recent_settlements: list[SettlementResult],
        stale_tolerance_seconds: float = 300.0,
    ) -> Observation:
        """
        Build an observation visible at sim_time.

        Only includes:
          - markets with a non-None snapshot where snapshot_time <= sim_time
          - snapshots not older than stale_tolerance_seconds
          - active or recently resolved markets
        """
        visible: dict[str, MarketSnapshot] = {}

        for mkey, state in market_states.items():
            snap = state.latest_snapshot
            if snap is None:
                continue

            # Enforce no-future-data: snapshot must predate current sim time
            if snap.snapshot_time > sim_time:
                continue

            # Drop excessively stale quotes
            age_seconds = (sim_time - snap.snapshot_time).total_seconds()
            if age_seconds > stale_tolerance_seconds and state.status == MarketStatus.ACTIVE:
                continue

            visible[mkey] = snap

        # Detect simple arb opportunities from visible market data
        opportunities = _detect_opportunities(visible)

        return Observation(
            sim_time=sim_time,
            visible_markets=visible,
            opportunities=opportunities,
            portfolio=portfolio,
            recent_fills=recent_fills,
            recent_settlements=recent_settlements,
        )


def _detect_opportunities(
    visible: dict[str, MarketSnapshot],
) -> list[dict]:
    """
    Detect simple binary arbitrage opportunities from current visible prices.

    An opportunity exists when, for two markets A and B on the same event:
      ask_A(Yes) + ask_B(No) < 1.0  (or ask_A(No) + ask_B(Yes) < 1.0)

    This is a lightweight pre-filter. Phase 3 validation is the real arbiter.
    """
    opportunities = []
    market_list = list(visible.items())

    for i in range(len(market_list)):
        for j in range(i + 1, len(market_list)):
            key_a, snap_a = market_list[i]
            key_b, snap_b = market_list[j]

            if snap_a.status != MarketStatus.ACTIVE or snap_b.status != MarketStatus.ACTIVE:
                continue

            opp = _check_binary_arb(key_a, snap_a, key_b, snap_b)
            if opp:
                opportunities.append(opp)

    return opportunities


def _check_binary_arb(
    key_a: str,
    snap_a: MarketSnapshot,
    key_b: MarketSnapshot,
    snap_b: MarketSnapshot,
) -> dict | None:
    """Check if a binary arb exists between two markets."""
    # For equivalent markets: buy Yes on A, buy Yes on B; combined cost < 1.0 means arb
    # Actually for complementary: buy Yes on A + buy No on B (or vice versa)

    # Try: Yes_A + No_B (direct equivalent markets)
    ask_yes_a = snap_a.best_ask.get("Yes") or snap_a.best_ask.get("yes")
    ask_yes_b = snap_b.best_ask.get("Yes") or snap_b.best_ask.get("yes")
    ask_no_a = snap_a.best_ask.get("No") or snap_a.best_ask.get("no")
    ask_no_b = snap_b.best_ask.get("No") or snap_b.best_ask.get("no")

    if ask_yes_a is not None and ask_no_b is not None:
        cost = ask_yes_a + ask_no_b
        fee_est = (snap_a.fees + snap_b.fees)
        net = 1.0 - cost - fee_est
        if net > 0.005:
            return {
                "type": "binary_pair",
                "market_a": key_a,
                "market_b": key_b,
                "leg_a": {"outcome": "Yes", "price": ask_yes_a},
                "leg_b": {"outcome": "No", "price": ask_no_b},
                "gross_profit": 1.0 - cost,
                "estimated_fees": fee_est,
                "net_profit_estimate": net,
            }

    if ask_no_a is not None and ask_yes_b is not None:
        cost = ask_no_a + ask_yes_b
        fee_est = (snap_a.fees + snap_b.fees)
        net = 1.0 - cost - fee_est
        if net > 0.005:
            return {
                "type": "binary_pair",
                "market_a": key_a,
                "market_b": key_b,
                "leg_a": {"outcome": "No", "price": ask_no_a},
                "leg_b": {"outcome": "Yes", "price": ask_yes_b},
                "gross_profit": 1.0 - cost,
                "estimated_fees": fee_est,
                "net_profit_estimate": net,
            }

    return None
