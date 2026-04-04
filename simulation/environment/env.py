"""
Simulation environment — main orchestration class.

The SimulationEnvironment is the central controller that:
  1. Maintains the simulation clock
  2. Processes historical events in order
  3. Updates visible market state
  4. Exposes observations to the strategy
  5. Accepts and routes trade actions
  6. Delegates fills to the execution engine
  7. Triggers settlements on market resolution
  8. Logs all state transitions

API:
    env = SimulationEnvironment(config, replay_stream)
    env.reset()
    while not env.is_done():
        obs = env.get_observation()
        actions = strategy.decide(obs)
        env.apply_actions(actions)
        env.advance()
    result = env.finalize()
"""

from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timezone

from simulation.config import SimulationConfig
from simulation.data.replay_stream import ReplayStream
from simulation.environment.clock import SimClock
from simulation.environment.observation import ObservationBuilder
from simulation.environment.state import StateManager
from simulation.execution.fill_engine import FillEngine
from simulation.models import (
    BacktestResult,
    EventType,
    FillResult,
    FillStatus,
    MarketStatus,
    Observation,
    SettlementResult,
    TradeAction,
)
from simulation.portfolio.account import Account

logger = logging.getLogger(__name__)

# How many events to process per advance() step
_EVENTS_PER_STEP = 50


class SimulationEnvironment:
    """
    Historical replay environment for backtesting arbitrage strategies.
    """

    def __init__(
        self,
        config: SimulationConfig,
        replay_stream: ReplayStream,
    ) -> None:
        self.config = config
        self._stream = replay_stream
        self._clock = SimClock()
        self._state_manager = StateManager()
        self._account = Account(initial_capital=config.initial_capital)
        self._fill_engine = FillEngine(config=config)
        self._obs_builder = ObservationBuilder()

        self._recent_fills: list[FillResult] = []
        self._recent_settlements: list[SettlementResult] = []
        self._all_fills: list[FillResult] = []
        self._all_settlements: list[SettlementResult] = []

        self._run_start: float = 0.0
        self._done = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> None:
        """Reset environment to the beginning of the replay window."""
        self._stream.reset()
        self._state_manager.reset()
        self._account.reset(self.config.initial_capital)
        self._fill_engine.reset()
        self._recent_fills = []
        self._recent_settlements = []
        self._all_fills = []
        self._all_settlements = []
        self._done = False
        self._run_start = _time.monotonic()

        # Determine start time
        first_ts, _ = self._stream.time_bounds()
        t_start = start_time or self.config.start_time or first_ts
        if t_start:
            self._clock.reset(t_start)
        logger.info("Environment reset. Clock: %s", self._clock)

    def get_observation(self) -> Observation:
        """Return the current observation visible to the strategy."""
        portfolio = self._account.get_portfolio_state()
        return self._obs_builder.build(
            sim_time=self._clock.now,
            market_states=self._state_manager.all_states(),
            portfolio=portfolio,
            recent_fills=list(self._recent_fills),
            recent_settlements=list(self._recent_settlements),
            stale_tolerance_seconds=self.config.stale_quote_tolerance_seconds,
        )

    def apply_actions(self, actions: list[TradeAction]) -> list[FillResult]:
        """
        Submit trade actions to the fill engine.
        Returns fill results for this timestep.
        """
        self._recent_fills = []
        if not actions:
            return []

        current_states = self._state_manager.all_states()

        for action in actions:
            fill = self._fill_engine.process_action(
                action=action,
                market_states=current_states,
                sim_time=self._clock.now,
            )
            self._recent_fills.append(fill)
            self._all_fills.append(fill)

            # Update account (compare enum members, not strings)
            if fill.fill_status in (FillStatus.FILLED, FillStatus.PARTIAL):
                self._account.apply_fill(fill)

        return list(self._recent_fills)

    def advance(self) -> int:
        """
        Consume all historical events at the NEXT distinct timestamp, then pause.

        This means each advance() call moves the clock forward by exactly one
        unique timestamp, giving the strategy a chance to observe and act at
        every meaningful market update.

        Returns number of events processed.
        """
        if self._done:
            return 0

        self._recent_settlements = []
        events_processed = 0

        # Peek to determine the target timestamp
        next_ev = self._stream.peek()
        if next_ev is None:
            self._done = True
            return 0

        target_ts = next_ev.timestamp

        # Process all events that share this timestamp
        while True:
            ev = self._stream.peek()
            if ev is None or ev.timestamp > target_ts:
                break

            self._stream.next_event()  # consume

            try:
                self._clock.tick(ev.timestamp)
            except ValueError:
                logger.warning("Out-of-order event skipped: %s", ev.event_id)
                continue

            self._state_manager.apply_event(ev)
            events_processed += 1

            if ev.event_type == EventType.MARKET_RESOLVED:
                settlements = self._process_settlement(ev)
                self._recent_settlements.extend(settlements)
                self._all_settlements.extend(settlements)

        # Update unrealized PnL
        self._account.mark_to_market(self._state_manager.all_states())
        self._state_manager.increment_step()

        end_time = self.config.end_time
        if end_time and self._clock.now >= end_time:
            self._done = True

        if not self._stream.has_next():
            self._done = True

        return events_processed

    def is_done(self) -> bool:
        return self._done

    def finalize(self) -> BacktestResult:
        """Settle remaining open positions and compute final metrics."""
        from simulation.analytics.metrics import compute_metrics

        # Force-settle any remaining open baskets at last known prices
        self._account.force_close_open_baskets(
            market_states=self._state_manager.all_states(),
            sim_time=self._clock.now,
        )

        portfolio = self._account.get_portfolio_state()
        metrics = compute_metrics(
            initial_capital=self.config.initial_capital,
            portfolio=portfolio,
            fill_log=self._all_fills,
            settlement_log=self._all_settlements,
        )

        _, last_ts = self._stream.time_bounds()
        run_secs = _time.monotonic() - self._run_start

        first_ts, _ = self._stream.time_bounds()

        return BacktestResult(
            start_time=self._clock.now if first_ts is None else first_ts,
            end_time=last_ts or self._clock.now,
            metrics=metrics,
            trade_log=self._all_fills,
            settlement_log=self._all_settlements,
            final_portfolio=portfolio,
            events_processed=self._state_manager._event_count,
            run_duration_seconds=run_secs,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_settlement(self, resolution_event) -> list[SettlementResult]:
        """Trigger settlement for all open positions in the resolved market."""
        mkey = f"{resolution_event.platform}::{resolution_event.market_id}"
        market_state = self._state_manager.get_state(mkey)
        if market_state is None or market_state.status != MarketStatus.RESOLVED:
            return []

        settlements = self._account.settle_market(
            platform=resolution_event.platform,
            market_id=resolution_event.market_id,
            resolution_outcome=market_state.resolution_outcome or "",
            resolution_value=market_state.resolution_value or 0.0,
            settlement_time=resolution_event.timestamp,
        )
        logger.info(
            "Settlement: %d positions settled for market %s",
            len(settlements), mkey,
        )
        return settlements
