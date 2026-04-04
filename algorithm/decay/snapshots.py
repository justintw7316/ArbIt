"""Stage A — Snapshot Collection Layer.

Consumes matched pairs from Stage 1 (Phase 4) and records time-stamped
spread observations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from algorithm.db import get_db
from algorithm.decay.config import PAIR_SNAPSHOTS_COL, SNAPSHOT_MIN_INTERVAL_SECONDS
from algorithm.decay.models import PairSnapshot


def _latest_snapshot_ts(pair_id: str) -> datetime | None:
    """Return timestamp of the most recent snapshot for *pair_id*, or None."""
    db = get_db()
    doc = db[PAIR_SNAPSHOTS_COL].find_one(
        {"pair_id": pair_id},
        {"timestamp": 1, "_id": 0},
        sort=[("timestamp", -1)],
    )
    if doc:
        return doc["timestamp"]
    return None


def should_collect(pair_id: str, now: datetime | None = None) -> bool:
    """Return True if enough time has elapsed since the last snapshot."""
    now = now or datetime.utcnow()
    last = _latest_snapshot_ts(pair_id)
    if last is None:
        return True
    return (now - last).total_seconds() >= SNAPSHOT_MIN_INTERVAL_SECONDS


def collect_snapshot(signal: dict[str, Any], now: datetime | None = None) -> PairSnapshot:
    """Build a PairSnapshot from a Phase 4 ArbitrageSignal dict.

    The *signal* dict is expected to have at least:
      pair_id, market_a_id, market_b_id, platform_a, platform_b,
      price_a, price_b, raw_spread
    """
    now = now or datetime.utcnow()
    price_a = float(signal["price_a"])
    price_b = float(signal["price_b"])
    raw = price_a - price_b

    snap = PairSnapshot(
        pair_id=signal["pair_id"],
        timestamp=now,
        market_a_id=signal["market_a_id"],
        market_b_id=signal["market_b_id"],
        platform_a=str(signal["platform_a"]),
        platform_b=str(signal["platform_b"]),
        price_a=price_a,
        price_b=price_b,
        raw_spread=round(raw, 6),
        abs_spread=round(abs(raw), 6),
        liquidity_a=signal.get("liquidity_a"),
        liquidity_b=signal.get("liquidity_b"),
        best_bid_a=signal.get("best_bid_a"),
        best_ask_a=signal.get("best_ask_a"),
        best_bid_b=signal.get("best_bid_b"),
        best_ask_b=signal.get("best_ask_b"),
    )
    return snap


def persist_snapshot(snap: PairSnapshot) -> None:
    """Insert a snapshot document into MongoDB."""
    db = get_db()
    db[PAIR_SNAPSHOTS_COL].insert_one(snap.model_dump(mode="json"))


def get_snapshots(
    pair_id: str,
    since: datetime | None = None,
    limit: int = 5000,
) -> list[PairSnapshot]:
    """Return chronologically-ordered snapshots for a pair."""
    db = get_db()
    query: dict[str, Any] = {"pair_id": pair_id}
    if since:
        query["timestamp"] = {"$gte": since}
    docs = list(
        db[PAIR_SNAPSHOTS_COL]
        .find(query, {"_id": 0})
        .sort("timestamp", 1)
        .limit(limit)
    )
    return [PairSnapshot(**d) for d in docs]
