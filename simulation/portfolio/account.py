"""
Account — the central portfolio/accounting engine.

Responsibilities:
  - Track cash, locked capital, realized/unrealized PnL
  - Open positions from fills
  - Process market settlements
  - Provide PortfolioState snapshots
  - Mark-to-market open positions
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from simulation.execution.baskets import BasketTracker
from simulation.execution.settlement import SettlementEngine
from simulation.models import (
    ArbBasket,
    BasketStatus,
    FillResult,
    FillStatus,
    MarketState,
    MarketStatus,
    PortfolioState,
    Position,
    SettlementResult,
)
from simulation.portfolio.positions import PositionRegistry

logger = logging.getLogger(__name__)


class Account:
    """Manages cash, positions, and basket lifecycle."""

    def __init__(self, initial_capital: float = 10_000.0) -> None:
        self._initial_capital = initial_capital
        self._cash: float = initial_capital
        self._locked_capital: float = 0.0
        self._realized_pnl: float = 0.0
        self._total_fees_paid: float = 0.0
        self._basket_payouts: dict[str, float] = {}

        self._positions = PositionRegistry()
        self._baskets = BasketTracker()
        self._settlement_engine = SettlementEngine()

        # Equity curve samples: list of (timestamp_iso, equity)
        self._equity_samples: list[tuple[str, float]] = []

    def reset(self, initial_capital: float) -> None:
        self._cash = initial_capital
        self._locked_capital = 0.0
        self._realized_pnl = 0.0
        self._total_fees_paid = 0.0
        self._basket_payouts.clear()
        self._positions.reset()
        self._baskets.reset()
        self._equity_samples.clear()

    def apply_fill(self, fill: FillResult) -> None:
        """Update account state when a fill arrives."""
        if fill.fill_status == FillStatus.REJECTED:
            return

        # Lock trade notional immediately. Fees are tracked now but realized
        # only when the basket closes, so cash-on-fill reflects just deployed
        # capital while final equity still absorbs execution fees.
        cost = fill.locked_capital
        self._cash -= cost
        self._locked_capital += cost
        self._total_fees_paid += fill.total_fees

        # Open positions
        self._positions.open_from_fill(fill)

        # Register basket
        basket = self._baskets.open_basket(fill, created_time=fill.fill_time)
        if basket:
            logger.debug(
                "Account: basket %s opened, locked=%.4f",
                fill.basket_id, cost,
            )

    def settle_market(
        self,
        platform: str,
        market_id: str,
        resolution_outcome: str,
        resolution_value: float,
        settlement_time: datetime,
    ) -> list[SettlementResult]:
        """Process settlement for all positions in a resolved market."""
        open_positions = self._positions.positions_for_market(platform, market_id)

        settlements = self._settlement_engine.settle_positions(
            positions=open_positions,
            platform=platform,
            market_id=market_id,
            resolution_outcome=resolution_outcome,
            resolution_value=resolution_value,
            settlement_time=settlement_time,
        )

        # Apply payouts
        for result in settlements:
            self._cash += result.net_payout
            pos_id = result.leg_id
            self._positions.close_position(pos_id, result.payout_per_share, settlement_time)
            if result.basket_id:
                self._basket_payouts[result.basket_id] = (
                    self._basket_payouts.get(result.basket_id, 0.0) + result.net_payout
                )

        # Close settled baskets
        for basket_id in {result.basket_id for result in settlements if result.basket_id}:
            basket = self._baskets.get_open(basket_id)
            if basket:
                basket_still_open = any(
                    pos.basket_id == basket_id for pos in self._positions.all_open()
                )
                if basket_still_open:
                    continue

                locked = basket.locked_capital
                fees = basket.total_fees
                total_payout = self._basket_payouts.pop(basket_id, 0.0)
                self._locked_capital -= locked
                self._cash -= fees
                pnl = total_payout - locked - fees
                self._realized_pnl += pnl
                self._baskets.close_basket(basket_id, pnl, settlement_time)

        return settlements

    def mark_to_market(self, market_states: dict[str, MarketState]) -> None:
        """Update unrealized PnL for all open positions."""
        self._positions.mark_to_market(market_states)

    def force_close_open_baskets(
        self,
        market_states: dict[str, MarketState],
        sim_time: datetime,
    ) -> None:
        """
        At end of simulation, force-close any remaining open baskets at mid-price.
        This handles positions that never resolved during the replay window.
        """
        for basket in self._baskets.all_open():
            total_value = 0.0
            for leg in basket.legs:
                if leg.fill_status != FillStatus.FILLED:
                    continue
                mkey = f"{leg.platform}::{leg.market_id}"
                state = market_states.get(mkey)
                if state and state.latest_snapshot:
                    mid = state.latest_snapshot.mid_price(leg.outcome) or 0.0
                else:
                    mid = leg.fill_price or 0.0
                total_value += mid * (leg.filled_size or 0.0)

            locked = basket.locked_capital
            fees = basket.total_fees
            self._locked_capital = max(0.0, self._locked_capital - locked)
            self._cash += total_value - fees
            pnl = total_value - locked - fees
            self._realized_pnl += pnl
            self._baskets.close_basket(basket.basket_id, pnl, sim_time)

    def snapshot_equity(self, sim_time: datetime) -> None:
        """Record current equity to the equity curve."""
        equity = self.total_equity
        self._equity_samples.append((sim_time.isoformat(), equity))

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def locked_capital(self) -> float:
        return self._locked_capital

    @property
    def unrealized_pnl(self) -> float:
        return self._positions.total_unrealized_pnl

    @property
    def total_equity(self) -> float:
        return self._cash + self._locked_capital + self.unrealized_pnl

    def get_portfolio_state(self) -> PortfolioState:
        return PortfolioState(
            cash=self._cash,
            locked_capital=self._locked_capital,
            total_equity=self.total_equity,
            realized_pnl=self._realized_pnl,
            unrealized_pnl=self.unrealized_pnl,
            total_fees_paid=self._total_fees_paid,
            open_baskets=self._baskets.all_open(),
            closed_baskets=self._baskets.all_closed(),
            positions=self._positions.all_open(),
        )
