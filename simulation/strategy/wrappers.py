"""
Strategy wrappers and built-in strategies for testing.

Includes:
  NullStrategy       — always returns empty actions (baseline)
  GreedyArbStrategy  — enters every detected opportunity at max allowed size
  ThresholdArbStrategy — enters opportunities above a profit threshold
  LoggingWrapper     — wraps any strategy and logs its decisions
"""

from __future__ import annotations

import logging
import uuid
from datetime import timezone

from simulation.models import (
    ArbBasket,
    BasketLeg,
    Observation,
    OrderSide,
    TradeAction,
)
from simulation.strategy.interface import BaseStrategy

logger = logging.getLogger(__name__)


class NullStrategy(BaseStrategy):
    """Does nothing — useful as a baseline or placeholder."""

    def decide(self, observation: Observation) -> list[TradeAction]:
        return []


class GreedyArbStrategy(BaseStrategy):
    """
    Enters every arb opportunity detected in the observation.

    Simple greedy strategy for testing the execution pipeline:
    - Takes every opportunity with net_profit_estimate > 0
    - Sizes each leg at max_size_per_leg
    - Does not manage existing positions
    """

    def __init__(
        self,
        max_size_per_leg: float = 10.0,
        min_net_profit: float = 0.005,
    ) -> None:
        self._max_size = max_size_per_leg
        self._min_profit = min_net_profit
        self._entered_pairs: set[frozenset[str]] = set()

    def decide(self, observation: Observation) -> list[TradeAction]:
        actions: list[TradeAction] = []

        for opp in observation.opportunities:
            net = opp.get("net_profit_estimate", 0.0)
            if net < self._min_profit:
                continue

            market_a = opp.get("market_a", "")
            market_b = opp.get("market_b", "")
            pair_key = frozenset([market_a, market_b])

            # Don't re-enter the same pair while it's in observation.portfolio
            open_basket_pairs = {
                frozenset(
                    f"{l.platform}::{l.market_id}"
                    for l in basket.legs
                )
                for basket in observation.portfolio.open_baskets
            }
            if pair_key in open_basket_pairs:
                continue

            leg_a_info = opp.get("leg_a", {})
            leg_b_info = opp.get("leg_b", {})
            if not leg_a_info or not leg_b_info:
                continue

            snap_a = observation.visible_markets.get(market_a)
            snap_b = observation.visible_markets.get(market_b)
            if snap_a is None or snap_b is None:
                continue

            # Parse market_key as "platform::market_id"
            parts_a = market_a.split("::", 1)
            parts_b = market_b.split("::", 1)
            if len(parts_a) != 2 or len(parts_b) != 2:
                continue

            basket_id = str(uuid.uuid4())
            action_id = str(uuid.uuid4())

            leg_a = BasketLeg(
                leg_id=str(uuid.uuid4()),
                platform=parts_a[0],
                market_id=parts_a[1],
                outcome=leg_a_info["outcome"],
                side=OrderSide.BUY,
                requested_size=self._max_size,
                requested_price=leg_a_info.get("price"),
            )
            leg_b = BasketLeg(
                leg_id=str(uuid.uuid4()),
                platform=parts_b[0],
                market_id=parts_b[1],
                outcome=leg_b_info["outcome"],
                side=OrderSide.BUY,
                requested_size=self._max_size,
                requested_price=leg_b_info.get("price"),
            )

            action = TradeAction(
                action_id=action_id,
                basket_id=basket_id,
                legs=[leg_a, leg_b],
                requested_time=observation.sim_time,
                min_profit_threshold=self._min_profit,
                max_size=self._max_size,
            )
            actions.append(action)
            logger.info(
                "GreedyArbStrategy: submitting action for opp net=%.4f", net
            )

        return actions

    def on_reset(self) -> None:
        self._entered_pairs.clear()


class ThresholdArbStrategy(BaseStrategy):
    """
    Like GreedyArbStrategy but filters on a stricter profit threshold
    and limits open basket count.
    """

    def __init__(
        self,
        min_net_profit: float = 0.02,
        max_size_per_leg: float = 50.0,
        max_open_baskets: int = 5,
    ) -> None:
        self._min_profit = min_net_profit
        self._max_size = max_size_per_leg
        self._max_open = max_open_baskets
        self._greedy = GreedyArbStrategy(
            max_size_per_leg=max_size_per_leg,
            min_net_profit=min_net_profit,
        )

    def decide(self, observation: Observation) -> list[TradeAction]:
        if len(observation.portfolio.open_baskets) >= self._max_open:
            return []
        return self._greedy.decide(observation)


class LoggingWrapper(BaseStrategy):
    """Wraps any strategy and logs decisions."""

    def __init__(self, inner: BaseStrategy) -> None:
        self._inner = inner

    def decide(self, observation: Observation) -> list[TradeAction]:
        actions = self._inner.decide(observation)
        if actions:
            logger.info(
                "Strategy @ %s: %d actions submitted",
                observation.sim_time.isoformat(), len(actions),
            )
        return actions

    def on_fill(self, fill_results: list) -> None:
        for fr in fill_results:
            logger.info("Fill: basket=%s status=%s", fr.basket_id, fr.fill_status)
        self._inner.on_fill(fill_results)

    def on_settlement(self, settlement_results: list) -> None:
        self._inner.on_settlement(settlement_results)
