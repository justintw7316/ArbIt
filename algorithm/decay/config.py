"""Configuration constants for the Arbitrage Decay Monitor."""

from __future__ import annotations

import os

# --- Episode thresholds ---
# Spread must exceed this to open an episode (absolute probability units)
EPISODE_OPEN_THRESHOLD: float = float(os.getenv("DECAY_OPEN_THRESHOLD", "0.02"))

# Spread must drop below this to close an episode
EPISODE_CLOSE_THRESHOLD: float = float(os.getenv("DECAY_CLOSE_THRESHOLD", "0.005"))

# Maximum episode duration before auto-expiry (seconds).  Default 24 h.
EPISODE_MAX_DURATION_SECONDS: float = float(
    os.getenv("DECAY_MAX_DURATION_S", str(24 * 3600))
)

# --- Snapshot collection ---
# Minimum interval between snapshots for the same pair (seconds)
SNAPSHOT_MIN_INTERVAL_SECONDS: float = float(
    os.getenv("DECAY_SNAPSHOT_INTERVAL_S", "60")
)

# --- Baseline ---
# Minimum closed episodes required before computing a pair-level baseline
BASELINE_MIN_EPISODES: int = int(os.getenv("DECAY_BASELINE_MIN_EPISODES", "3"))

# --- Persistence score ---
# Weight applied to elapsed time in persistence formula
PERSISTENCE_TIME_WEIGHT: float = float(os.getenv("DECAY_PERSISTENCE_TIME_W", "0.4"))

# Weight applied to remaining-spread ratio in persistence formula
PERSISTENCE_SPREAD_WEIGHT: float = float(
    os.getenv("DECAY_PERSISTENCE_SPREAD_W", "0.6")
)

# --- MongoDB collection names ---
PAIR_SNAPSHOTS_COL = "pair_snapshots"
SPREAD_EPISODES_COL = "spread_episodes"
EPISODE_DECAY_METRICS_COL = "episode_decay_metrics"
PAIR_DECAY_BASELINES_COL = "pair_decay_baselines"
