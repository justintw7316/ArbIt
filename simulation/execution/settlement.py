"""
Settlement engine — computes payouts when markets resolve.

For each open position in a resolved market:
  - If outcome matches resolution_outcome: payout = 1.0 * shares
  - Otherwise: payout = 0.0
  - net_payout = gross_payout - platform settlement fee (if any)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from simulation.models import (
    BasketLeg,
    FillStatus,
    OrderSide,
    Position,
    SettlementResult,
)

logger = logging.getLogger(__name__)


class SettlementEngine:
    """Computes settlement payouts for resolved market positions."""

    def settle_positions(
        self,
        positions: list[Position],
        platform: str,
        market_id: str,
        resolution_outcome: str,
        resolution_value: float,
        settlement_time: datetime,
    ) -> list[SettlementResult]:
        """
        Compute settlement for all positions in a resolved market.

        Args:
            positions: all open positions (will be filtered to this market)
            platform: resolving platform
            market_id: resolving market
            resolution_outcome: the winning outcome label
            resolution_value: payout per share for the winning outcome (typically 1.0)
            settlement_time: time of settlement

        Returns:
            List of SettlementResult, one per settled position.
        """
        results: list[SettlementResult] = []

        for pos in positions:
            if pos.platform != platform or pos.market_id != market_id:
                continue

            # Determine if this position wins
            if pos.outcome == resolution_outcome:
                payout_per_share = resolution_value
            else:
                payout_per_share = 1.0 - resolution_value  # 0.0 if binary

            gross_payout = payout_per_share * pos.size
            fees_deducted = 0.0  # settlement fees typically zero on prediction markets
            net_payout = gross_payout - fees_deducted

            result = SettlementResult(
                basket_id=pos.basket_id or "",
                leg_id=pos.position_id,
                platform=platform,
                market_id=market_id,
                outcome=pos.outcome,
                resolution_outcome=resolution_outcome,
                payout_per_share=payout_per_share,
                shares_held=pos.size,
                gross_payout=gross_payout,
                fees_deducted=fees_deducted,
                net_payout=net_payout,
                settlement_time=settlement_time,
            )
            results.append(result)
            logger.debug(
                "Settlement: %s %s %s → payout=%.4f",
                platform, market_id, pos.outcome, net_payout,
            )

        return results
