"""Data models for the Arbitrage Decay Monitor."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EpisodeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    REVERSED = "reversed"
    EXPIRED = "expired"


class DecayStatus(str, Enum):
    OPENING = "opening"
    ACTIVELY_DECAYING = "actively_decaying"
    SLOW_DECAY = "slow_decay"
    STALLED = "stalled"
    RE_WIDENING = "re_widening"
    MOSTLY_CLOSED = "mostly_closed"


# ---------------------------------------------------------------------------
# Stage A — Pair Snapshot
# ---------------------------------------------------------------------------

class PairSnapshot(BaseModel):
    """A single time-stamped price observation for a matched pair."""

    pair_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    market_a_id: str
    market_b_id: str
    platform_a: str
    platform_b: str
    price_a: float
    price_b: float
    midpoint_a: float | None = None
    midpoint_b: float | None = None
    raw_spread: float
    abs_spread: float
    liquidity_a: float | None = None
    liquidity_b: float | None = None
    best_bid_a: float | None = None
    best_ask_a: float | None = None
    best_bid_b: float | None = None
    best_ask_b: float | None = None


# ---------------------------------------------------------------------------
# Stage B — Spread Episode
# ---------------------------------------------------------------------------

class SpreadEpisode(BaseModel):
    """A contiguous period where a spread exceeds thresholds."""

    episode_id: str
    pair_id: str
    start_time: datetime
    end_time: datetime | None = None
    opening_spread: float
    peak_spread: float
    current_spread: float
    closing_spread: float | None = None
    duration_seconds: float = 0.0
    status: EpisodeStatus = EpisodeStatus.OPEN
    snapshot_count: int = 0


# ---------------------------------------------------------------------------
# Stage C — Decay Metrics
# ---------------------------------------------------------------------------

class EpisodeDecayMetrics(BaseModel):
    """Computed decay statistics for a single episode."""

    episode_id: str
    pair_id: str
    opening_spread: float
    peak_spread: float
    current_spread: float
    percent_decay: float
    time_since_open_seconds: float
    time_to_peak_seconds: float
    decay_velocity: float
    persistence_score: float
    half_life_seconds: float | None = None


# ---------------------------------------------------------------------------
# Stage D — Historical Baseline
# ---------------------------------------------------------------------------

class PairDecayBaseline(BaseModel):
    """Aggregate baseline stats for a pair (or pair group)."""

    pair_id: str
    platform_a: str
    platform_b: str
    episode_count: int = 0
    median_opening_spread: float = 0.0
    median_half_life_seconds: float | None = None
    median_time_to_close_seconds: float | None = None
    avg_percent_decay_5m: float | None = None
    avg_percent_decay_15m: float | None = None
    avg_percent_decay_30m: float | None = None
    persistence_p25: float | None = None
    persistence_p50: float | None = None
    persistence_p75: float | None = None
    typical_peak_spread: float | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Stage E — Investor Signal
# ---------------------------------------------------------------------------

class DecaySignal(BaseModel):
    """Investor-facing summary for a single active episode."""

    episode_id: str
    pair_id: str
    platform_a: str
    platform_b: str
    text_a: str = ""
    text_b: str = ""
    current_spread: float
    opening_spread: float
    peak_spread: float
    percent_decay: float
    half_life_seconds: float | None = None
    duration_seconds: float
    persistence_score: float
    persistence_percentile: float | None = None
    decay_status: DecayStatus
    urgency_score: float
    relative_abnormality_score: float | None = None
    summary: str = ""
    start_time: datetime
    snapshot_count: int = 0
