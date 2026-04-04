"""
Replay stream: time-ordered iterator over HistoricalReplayEvents.

Guarantees:
- Events are yielded in strictly non-decreasing timestamp order.
- Duplicate events (same event_id) are de-duplicated.
- Optional time-range filtering.
- Supports both eager (list) and lazy (generator) modes.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Generator, Iterable

from simulation.models import HistoricalReplayEvent

logger = logging.getLogger(__name__)


class ReplayStream:
    """
    Wraps an iterable of HistoricalReplayEvents and exposes them in
    chronological order within an optional time window.

    Eager mode (default): sorts entire event list upfront.
    This is fine for historical backtests where the full dataset fits in memory.
    """

    def __init__(
        self,
        events: Iterable[HistoricalReplayEvent],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        deduplicate: bool = True,
    ) -> None:
        self._start_time = _ensure_tz(start_time)
        self._end_time = _ensure_tz(end_time)
        self._deduplicate = deduplicate
        self._events = self._build(events)
        self._index = 0

    def _build(self, raw: Iterable[HistoricalReplayEvent]) -> list[HistoricalReplayEvent]:
        events = list(raw)
        seen_ids: set[str] = set()
        filtered: list[HistoricalReplayEvent] = []

        for ev in events:
            ts = _ensure_tz(ev.timestamp)

            if self._deduplicate:
                if ev.event_id in seen_ids:
                    logger.debug("Skipping duplicate event_id=%s", ev.event_id)
                    continue
                seen_ids.add(ev.event_id)

            if self._start_time and ts < self._start_time:
                continue
            if self._end_time and ts > self._end_time:
                continue

            filtered.append(ev)

        filtered.sort(key=lambda e: _ensure_tz(e.timestamp))
        logger.info("ReplayStream: %d events loaded", len(filtered))
        return filtered

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Generator[HistoricalReplayEvent, None, None]:
        for ev in self._events:
            yield ev

    def peek(self) -> HistoricalReplayEvent | None:
        """Return next event without consuming it."""
        if self._index < len(self._events):
            return self._events[self._index]
        return None

    def next_event(self) -> HistoricalReplayEvent | None:
        """Consume and return the next event."""
        if self._index < len(self._events):
            ev = self._events[self._index]
            self._index += 1
            return ev
        return None

    def has_next(self) -> bool:
        return self._index < len(self._events)

    def reset(self) -> None:
        self._index = 0

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def total_events(self) -> int:
        return len(self._events)

    def time_bounds(self) -> tuple[datetime | None, datetime | None]:
        """Return (first_event_time, last_event_time)."""
        if not self._events:
            return None, None
        return (
            _ensure_tz(self._events[0].timestamp),
            _ensure_tz(self._events[-1].timestamp),
        )

    def events_until(self, cutoff: datetime) -> list[HistoricalReplayEvent]:
        """Return all remaining events up to (and including) cutoff time."""
        cutoff = _ensure_tz(cutoff)
        batch: list[HistoricalReplayEvent] = []
        while self._index < len(self._events):
            ev = self._events[self._index]
            if _ensure_tz(ev.timestamp) > cutoff:
                break
            batch.append(ev)
            self._index += 1
        return batch


def _ensure_tz(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
