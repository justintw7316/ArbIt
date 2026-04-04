"""Configuration constants for Phase 4 (and reused by Phase 5)."""

from __future__ import annotations

import os

# Minimum spread to consider a pair actionable (2 %)
MIN_SPREAD: float = float(os.getenv("MIN_SPREAD", "0.02"))

# How many days of price history to load for spread feature extraction
LOOKBACK_DAYS: int = int(os.getenv("LOOKBACK_DAYS", "30"))

# Fractional Kelly to use (0.5 = half-Kelly)
KELLY_FRACTION: float = float(os.getenv("KELLY_FRACTION", "0.5"))

# Hard cap: max fraction of bankroll per position
MAX_POSITION_FRACTION: float = float(os.getenv("MAX_POSITION_FRACTION", "0.10"))
