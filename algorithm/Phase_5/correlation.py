"""Price correlation validation for Phase 5.

Text similarity (Phase 3) tells us two markets *look* like the same event.
Price correlation tells us they *behave* like the same event.  If they match
textually but their prices move independently, the match is likely a false
positive.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np

from algorithm.Phase_4.config import LOOKBACK_DAYS

logger = logging.getLogger(__name__)


def compute_price_correlation(
    platform_a: str,
    market_id_a: str,
    platform_b: str,
    market_id_b: str,
    lookback_days: int = LOOKBACK_DAYS,
    min_points: int = 10,
) -> tuple[float, bool]:
    """Compute time-aware price correlation between two markets.

    Returns (score, is_valid).
    Returns (0.0, True) when insufficient history exists (benefit of the doubt).
    """
    try:
        from algorithm.db import get_db, PRICE_HISTORY_COL

        db = get_db()
        col = db[PRICE_HISTORY_COL]
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)

        hist_a = list(
            col.find({
                "platform": platform_a,
                "market_id": market_id_a,
                "timestamp": {"$gte": cutoff},
            }).sort("timestamp", 1)
        )
        hist_b = list(
            col.find({
                "platform": platform_b,
                "market_id": market_id_b,
                "timestamp": {"$gte": cutoff},
            }).sort("timestamp", 1)
        )
    except Exception as exc:
        logger.debug("Could not load price history for correlation: %s", exc)
        return 0.0, True

    if len(hist_a) < min_points or len(hist_b) < min_points:
        logger.debug(
            "Insufficient history for correlation: %d / %d points (need %d)",
            len(hist_a),
            len(hist_b),
            min_points,
        )
        return 0.0, True

    prices_a, prices_b = _align_prices(hist_a, hist_b)
    return compute_correlation_from_arrays(prices_a, prices_b, min_points=min_points)


def compute_correlation_from_arrays(
    prices_a: np.ndarray,
    prices_b: np.ndarray,
    min_points: int = 10,
) -> tuple[float, bool]:
    """Pure-numpy correlation computation (for testing / simulation)."""
    prices_a = np.asarray(prices_a, dtype=float)
    prices_b = np.asarray(prices_b, dtype=float)

    if len(prices_a) < min_points or len(prices_b) < min_points:
        return 0.0, True

    n = min(len(prices_a), len(prices_b))
    prices_a = prices_a[:n]
    prices_b = prices_b[:n]

    level_corr = _safe_corr(prices_a, prices_b)

    returns_a = np.diff(prices_a)
    returns_b = np.diff(prices_b)

    return_corr = _safe_corr(returns_a, returns_b) if len(returns_a) >= 2 else 0.0
    same_direction = _direction_agreement(returns_a, returns_b) if len(returns_a) else 0.0

    lagged_corr = 0.0
    if len(returns_a) >= 3 and len(returns_b) >= 3:
        lagged_corr = max(
            _safe_corr(returns_a[1:], returns_b[:-1]),
            _safe_corr(returns_a[:-1], returns_b[1:]),
        )

    score = (
        0.45 * level_corr
        + 0.30 * return_corr
        + 0.15 * lagged_corr
        + 0.10 * (2.0 * same_direction - 1.0)
    )
    score = round(float(max(-1.0, min(1.0, score))), 4)

    is_valid = score >= 0.60 and level_corr >= 0.40 and same_direction >= 0.55
    return score, is_valid


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 2 or len(b) < 2:
        return 0.0
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _direction_agreement(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return float(np.mean(np.sign(a[:n]) == np.sign(b[:n])))


def _align_prices(
    hist_a: list[dict], hist_b: list[dict]
) -> tuple[np.ndarray, np.ndarray]:
    """Align two price histories to shared hourly buckets."""

    def _bucket(ts: object) -> datetime:
        if isinstance(ts, datetime):
            return ts.replace(minute=0, second=0, microsecond=0)
        return datetime.fromisoformat(str(ts)).replace(minute=0, second=0, microsecond=0)

    buckets_a = {_bucket(doc["timestamp"]): float(doc["yes_price"]) for doc in hist_a}
    buckets_b = {_bucket(doc["timestamp"]): float(doc["yes_price"]) for doc in hist_b}

    common = sorted(set(buckets_a) & set(buckets_b))
    if not common:
        return np.array([]), np.array([])

    return (
        np.array([buckets_a[t] for t in common]),
        np.array([buckets_b[t] for t in common]),
    )
