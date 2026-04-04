"""
Environment state manager.

Maintains the collection of MarketState objects — one per known market.
The state manager is the authority on what is currently "visible" at
the current simulation time. It never exposes future data.
"""

from __future__ import annotations

import logging
from datetime import datetime

from simulation.models import (
    EnvironmentState,
    EventType,
    HistoricalReplayEvent,
    MarketState,
    MarketStatus,
)

logger = logging.getLogger(__name__)


class StateManager:
    """
    Applies historical replay events to maintain current market states.

    Invariant: states only reflect events with timestamp <= clock.now.
    """

    def __init__(self) -> None:
        self._states: dict[str, MarketState] = {}
        self._event_count: int = 0
        self._step_count: int = 0

    def apply_event(self, event: HistoricalReplayEvent) -> None:
        """Apply a single historical event, updating internal state."""
        self._event_count += 1
        mkey = f"{event.platform}::{event.market_id}"

        if event.event_type == EventType.MARKET_CREATED:
            self._handle_created(mkey, event)

        elif event.event_type in (EventType.MARKET_UPDATED, EventType.ORDERBOOK_SNAPSHOT):
            self._handle_updated(mkey, event)

        elif event.event_type == EventType.MARKET_RESOLVED:
            self._handle_resolved(mkey, event)

        elif event.event_type == EventType.TRADE_PRINT:
            self._handle_trade_print(mkey, event)

    def get_state(self, market_key: str) -> MarketState | None:
        return self._states.get(market_key)

    def all_states(self) -> dict[str, MarketState]:
        return dict(self._states)

    def active_states(self) -> dict[str, MarketState]:
        return {k: s for k, s in self._states.items()
                if s.status == MarketStatus.ACTIVE}

    def to_environment_state(self, current_time: datetime) -> EnvironmentState:
        return EnvironmentState(
            current_time=current_time,
            market_states=dict(self._states),
            event_count=self._event_count,
            step_count=self._step_count,
        )

    def increment_step(self) -> None:
        self._step_count += 1

    def reset(self) -> None:
        self._states.clear()
        self._event_count = 0
        self._step_count = 0

    # ------------------------------------------------------------------

    def _ensure_state(self, mkey: str, event: HistoricalReplayEvent) -> MarketState:
        if mkey not in self._states:
            self._states[mkey] = MarketState(
                market_id=event.market_id,
                platform=event.platform,
                status=MarketStatus.ACTIVE,
            )
        return self._states[mkey]

    def _handle_created(self, mkey: str, event: HistoricalReplayEvent) -> None:
        state = self._ensure_state(mkey, event)
        if event.snapshot:
            state.latest_snapshot = event.snapshot
        state.last_update_time = event.timestamp
        logger.debug("Market created: %s", mkey)

    def _handle_updated(self, mkey: str, event: HistoricalReplayEvent) -> None:
        state = self._ensure_state(mkey, event)
        if event.snapshot:
            # Only update if snapshot is newer than current
            current_snap = state.latest_snapshot
            if current_snap is None or event.timestamp >= state.last_update_time:  # type: ignore[operator]
                state.latest_snapshot = event.snapshot
        state.last_update_time = event.timestamp
        logger.debug("Market updated: %s @ %s", mkey, event.timestamp.isoformat())

    def _handle_resolved(self, mkey: str, event: HistoricalReplayEvent) -> None:
        state = self._ensure_state(mkey, event)
        state.status = MarketStatus.RESOLVED
        state.resolution_outcome = event.data.get("resolution_outcome")
        state.resolution_value = float(event.data.get("resolution_value", 0.0))
        state.resolution_time = event.timestamp
        state.last_update_time = event.timestamp
        logger.info(
            "Market resolved: %s → outcome=%s value=%.2f",
            mkey, state.resolution_outcome, state.resolution_value or 0.0,
        )

    def _handle_trade_print(self, mkey: str, event: HistoricalReplayEvent) -> None:
        state = self._ensure_state(mkey, event)
        # Update last_traded prices if present
        if state.latest_snapshot and event.data.get("price") and event.data.get("outcome"):
            outcome = event.data["outcome"]
            price = float(event.data["price"])
            state.latest_snapshot.last_traded[outcome] = price
        state.last_update_time = event.timestamp
