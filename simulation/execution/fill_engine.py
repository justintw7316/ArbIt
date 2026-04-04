"""
Fill engine — the core execution simulator.

Responsibilities:
  - Accept TradeActions from the strategy
  - Apply latency (optional)
  - Simulate fills using visible orderbook depth + slippage model
  - Apply fees
  - Support partial fills
  - Enforce capital and size constraints
  - Return FillResult with full execution detail

Does NOT maintain portfolio state — that is the Account's responsibility.
"""

from __future__ import annotations

import logging
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from simulation.config import SimulationConfig
from simulation.execution.fees import FeeCalculator
from simulation.execution.slippage import SlippageModel
from simulation.models import (
    ArbBasket,
    BasketLeg,
    BasketStatus,
    FillResult,
    FillStatus,
    MarketState,
    MarketStatus,
    OrderSide,
    RealismMode,
    TradeAction,
)

logger = logging.getLogger(__name__)


class FillEngine:
    """
    Simulates order execution for arbitrage basket TradeActions.
    """

    def __init__(self, config: SimulationConfig) -> None:
        self._config = config
        self._exec_params = config.execution_params()
        self._fee_calc = FeeCalculator(config)
        self._slip_model = SlippageModel(config)
        self._open_baskets: dict[str, ArbBasket] = {}

    def reset(self) -> None:
        self._open_baskets.clear()

    def process_action(
        self,
        action: TradeAction,
        market_states: dict[str, MarketState],
        sim_time: datetime,
    ) -> FillResult:
        """
        Attempt to fill a TradeAction and return a FillResult.

        Steps:
        1. Validate action (market active, capital available, min size)
        2. Simulate latency (advance effective fill time)
        3. Fill each leg using slippage model
        4. Compute fees
        5. Check profit threshold
        6. Return FillResult
        """
        effective_time = self._apply_latency(sim_time)

        # Validate
        rejection = self._validate_action(action, market_states, effective_time)
        if rejection:
            return FillResult(
                action_id=action.action_id,
                basket_id=action.basket_id,
                legs=[],
                fill_status=FillStatus.REJECTED,
                fill_time=effective_time,
                rejection_reason=rejection,
            )

        # Fill each leg
        filled_legs: list[BasketLeg] = []
        total_fees = 0.0
        total_slip = 0.0
        total_cost = 0.0
        any_partial = False
        any_failed = False

        snapshots = {
            k: s.latest_snapshot
            for k, s in market_states.items()
            if s.latest_snapshot is not None
        }

        for leg in action.legs:
            mkey = f"{leg.platform}::{leg.market_id}"
            snap = snapshots.get(mkey)
            filled_leg = deepcopy(leg)

            fill_price, filled_size, slip_cost = self._slip_model.adjusted_price(
                side=leg.side,
                outcome=leg.outcome,
                requested_size=leg.requested_size,
                snapshot=snap,
            )

            if filled_size <= 0:
                filled_leg.fill_status = FillStatus.REJECTED
                filled_leg.rejection_reason = "No liquidity at requested price"
                any_failed = True
                filled_legs.append(filled_leg)
                continue

            fee = self._fee_calc.leg_fee(filled_leg, fill_price, snap)
            total_fees += fee
            total_slip += slip_cost
            total_cost += fill_price * filled_size

            filled_leg.fill_price = fill_price
            filled_leg.filled_size = filled_size
            filled_leg.fees_paid = fee
            filled_leg.fill_time = effective_time
            filled_leg.fill_status = (
                FillStatus.FILLED
                if abs(filled_size - leg.requested_size) < 1e-6
                else FillStatus.PARTIAL
            )
            if filled_leg.fill_status == FillStatus.PARTIAL:
                any_partial = True

            filled_legs.append(filled_leg)
            logger.debug(
                "Leg filled: %s %s %s@%.4f (size=%.2f, fee=%.4f)",
                leg.platform, leg.outcome, leg.side, fill_price, filled_size, fee,
            )

        # Determine overall status
        if any_failed and not any(l.fill_status == FillStatus.FILLED for l in filled_legs):
            overall_status = FillStatus.REJECTED
        elif any_failed or any_partial:
            overall_status = FillStatus.PARTIAL
        else:
            overall_status = FillStatus.FILLED

        # Compute locked capital and expected profit
        locked_capital = total_cost
        expected_profit = self._compute_expected_profit(filled_legs, total_fees)

        # Check minimum profit threshold
        if (overall_status == FillStatus.FILLED
                and expected_profit < action.min_profit_threshold * locked_capital):
            return FillResult(
                action_id=action.action_id,
                basket_id=action.basket_id,
                legs=filled_legs,
                fill_status=FillStatus.REJECTED,
                total_fees=total_fees,
                total_slippage_cost=total_slip,
                locked_capital=locked_capital,
                expected_profit=expected_profit,
                fill_time=effective_time,
                rejection_reason=(
                    f"Profit {expected_profit:.4f} below threshold "
                    f"{action.min_profit_threshold * locked_capital:.4f}"
                ),
            )

        return FillResult(
            action_id=action.action_id,
            basket_id=action.basket_id,
            legs=filled_legs,
            fill_status=overall_status,
            total_fees=total_fees,
            total_slippage_cost=total_slip,
            locked_capital=locked_capital,
            expected_profit=expected_profit,
            fill_time=effective_time,
        )

    # ------------------------------------------------------------------

    def _apply_latency(self, sim_time: datetime) -> datetime:
        latency_ms = self._exec_params.latency_ms
        if latency_ms <= 0:
            return sim_time
        return sim_time + timedelta(milliseconds=latency_ms)

    def _validate_action(
        self,
        action: TradeAction,
        market_states: dict[str, MarketState],
        effective_time: datetime,
    ) -> str | None:
        """Return rejection reason string, or None if valid."""
        if not action.legs:
            return "Empty legs"

        for leg in action.legs:
            mkey = f"{leg.platform}::{leg.market_id}"
            state = market_states.get(mkey)
            if state is None:
                return f"Unknown market: {mkey}"
            if state.status != MarketStatus.ACTIVE:
                return f"Market not active: {mkey} (status={state.status})"
            if leg.requested_size < self._config.min_trade_size:
                return f"Size {leg.requested_size} below minimum {self._config.min_trade_size}"
            if leg.requested_size > self._config.max_basket_size:
                return (
                    f"Size {leg.requested_size} exceeds max basket size "
                    f"{self._config.max_basket_size}"
                )

        return None

    def _compute_expected_profit(
        self, filled_legs: list[BasketLeg], total_fees: float
    ) -> float:
        """
        Estimate expected profit from a binary arb basket.

        For a fully filled binary pair where one leg wins (payout=1.0):
          profit = 1.0 * max_leg_size - sum(leg_cost) - fees
        """
        if not filled_legs:
            return 0.0

        # Sum costs
        total_cost = sum(
            (l.fill_price or 0.0) * l.filled_size
            for l in filled_legs
            if l.fill_status in (FillStatus.FILLED, FillStatus.PARTIAL)
        )
        # Payout if exactly one leg wins (binary arb assumption)
        max_payout = max(
            (l.filled_size for l in filled_legs if l.fill_status == FillStatus.FILLED),
            default=0.0,
        )
        return max_payout - total_cost - total_fees
