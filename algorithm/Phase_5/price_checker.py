"""Live price re-checking for Phase 5.

Phase 4 computed signals using prices that may be stale.  Before executing
a trade we must confirm the spread still exists at the current market price.

NOTE: Phase 1 (data ingestion) is not yet implemented.  The fetch_live_price
function returns None when no live client is available; the validator handles
this gracefully by falling back to the Phase 4 prices.
"""

from __future__ import annotations

import logging

from algorithm.Phase_4.models import ArbitrageSignal, Platform

logger = logging.getLogger(__name__)


def fetch_live_price(platform: Platform, market_id: str) -> float | None:
    """Fetch the current YES price for a single market.

    Returns None if the fetch fails or Phase 1 clients are unavailable.
    The caller (TradeValidator) already handles None by falling back to
    the cached Phase 4 price.
    """
    try:
        # Try to use Phase 1 ingestion clients if they exist
        if platform == Platform.POLYMARKET:
            return _fetch_polymarket(market_id)
        elif platform == Platform.KALSHI:
            return _fetch_kalshi(market_id)
        elif platform == Platform.MANIFOLD:
            return _fetch_manifold(market_id)
    except Exception as exc:
        logger.warning(
            "Live price fetch failed for %s/%s: %s", platform.value, market_id, exc
        )
    return None


def _fetch_polymarket(market_id: str) -> float | None:
    """Fetch live price from Polymarket.  Stub until Phase 1 is implemented."""
    # Phase 1 not yet implemented — return None to signal fallback
    logger.debug("Polymarket live fetch not implemented (Phase 1 pending)")
    return None


def _fetch_kalshi(market_id: str) -> float | None:
    """Fetch live price from Kalshi.  Stub until Phase 1 is implemented."""
    logger.debug("Kalshi live fetch not implemented (Phase 1 pending)")
    return None


def _fetch_manifold(market_id: str) -> float | None:
    """Fetch live price from Manifold Markets."""
    try:
        import httpx

        resp = httpx.get(
            f"https://api.manifold.markets/v0/market/{market_id}", timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("probability", 0.5))
    except Exception as exc:
        logger.warning("Manifold fetch failed for %s: %s", market_id, exc)
        return None


def check_spread_still_exists(
    signal: ArbitrageSignal,
    live_a: float,
    live_b: float,
    min_spread: float = 0.02,
) -> tuple[float, bool]:
    """Compare live prices to see if the spread is still actionable.

    Returns (live_spread, still_exists).
    """
    live_spread = abs(live_a - live_b)
    still_exists = live_spread >= min_spread
    if not still_exists:
        logger.info(
            "Spread vanished for %s: was %.4f, now %.4f",
            signal.pair_id,
            signal.raw_spread,
            live_spread,
        )
    return round(live_spread, 6), still_exists
