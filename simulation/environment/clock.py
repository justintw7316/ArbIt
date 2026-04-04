"""
Simulation clock.

Tracks current simulated time and enforces the no-future-data invariant.
The clock only moves forward — calling tick() or set_time() to an earlier
timestamp raises an error.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SimClock:
    """Monotonically advancing simulation clock."""

    def __init__(self, start_time: datetime | None = None) -> None:
        self._time: datetime = _tz(start_time or datetime.min.replace(tzinfo=timezone.utc))

    @property
    def now(self) -> datetime:
        return self._time

    def tick(self, new_time: datetime) -> None:
        """Advance the clock to new_time. Raises if new_time is in the past."""
        new_time = _tz(new_time)
        if new_time < self._time:
            raise ValueError(
                f"Clock cannot go backwards: {new_time} < {self._time}"
            )
        if new_time > self._time:
            logger.debug("Clock: %s → %s", self._time.isoformat(), new_time.isoformat())
            self._time = new_time

    def reset(self, start_time: datetime) -> None:
        self._time = _tz(start_time)

    def __repr__(self) -> str:
        return f"SimClock(now={self._time.isoformat()})"


def _tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
