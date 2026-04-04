"""
Fee calculator.

Computes fees for a trade leg based on:
  - Platform-level fee rate (from market snapshot or config)
  - Realism-mode fee multiplier
  - Notional value of the trade
"""

from __future__ import annotations

from simulation.config import SimulationConfig
from simulation.models import BasketLeg, MarketSnapshot, RealismMode


class FeeCalculator:
    """Computes fees for individual legs and full baskets."""

    def __init__(self, config: SimulationConfig) -> None:
        self._exec_params = config.execution_params()

    def leg_fee(
        self,
        leg: BasketLeg,
        fill_price: float,
        snapshot: MarketSnapshot | None,
    ) -> float:
        """
        Compute fee for a single filled leg.

        Fee = max(platform_fee_rate, config_fee_bps/10000) * notional
        where notional = fill_price * filled_size.
        """
        platform_fee = snapshot.fees if snapshot else 0.0
        config_fee = self._exec_params.fee_bps / 10_000

        # Take the higher of platform and config fee (conservative)
        effective_fee_rate = max(platform_fee, config_fee)

        notional = fill_price * leg.requested_size
        return round(effective_fee_rate * notional, 6)

    def basket_fees(
        self,
        legs: list[BasketLeg],
        snapshots: dict[str, MarketSnapshot],
    ) -> float:
        """Total fees across all legs of a basket."""
        total = 0.0
        for leg in legs:
            mkey = f"{leg.platform}::{leg.market_id}"
            snap = snapshots.get(mkey)
            price = leg.fill_price or leg.requested_price or 0.5
            total += self.leg_fee(leg, price, snap)
        return total
