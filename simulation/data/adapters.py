"""
Data adapters: transform raw historical records from external sources into
normalized HistoricalReplayEvent objects.

Add a new adapter class per data source. The environment core never imports
source-specific formats — only the normalized event type.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from simulation.models import (
    EventType,
    FillStatus,
    HistoricalReplayEvent,
    MarketSnapshot,
    MarketStatus,
    OrderbookLevel,
)


def _parse_dt(value: Any) -> datetime:
    """Parse an ISO string or epoch int to a timezone-aware datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value).rstrip("Z")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Generic JSON adapter (our internal format)
# ---------------------------------------------------------------------------


class GenericJsonAdapter:
    """
    Adapts records from our internal JSON format:

    {
      "event_type": "market_updated",
      "platform": "polymarket",
      "market_id": "abc123",
      "timestamp": "2024-01-15T10:30:00Z",
      "data": {
        "question": "...",
        "outcomes": ["Yes", "No"],
        "best_bid": {"Yes": 0.44, "No": 0.54},
        "best_ask": {"Yes": 0.46, "No": 0.56},
        "last_traded": {"Yes": 0.45, "No": 0.55},
        "fees": 0.02,
        "close_time": "2024-06-01T00:00:00Z"
      }
    }

    Resolution events additionally carry:
    {
      "event_type": "market_resolved",
      ...
      "data": {
        "resolution_outcome": "Yes",
        "resolution_value": 1.0
      }
    }
    """

    def adapt(self, raw: dict[str, Any]) -> HistoricalReplayEvent:
        event_type_str = raw.get("event_type", "market_updated").lower()
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            event_type = EventType.MARKET_UPDATED

        platform = str(raw.get("platform", "unknown"))
        market_id = str(raw.get("market_id", ""))
        timestamp = _parse_dt(raw.get("timestamp", datetime.now(tz=timezone.utc)))
        data: dict[str, Any] = dict(raw.get("data", {}))
        event_id = raw.get("event_id") or str(uuid.uuid4())

        snapshot: MarketSnapshot | None = None
        if event_type in (EventType.MARKET_CREATED, EventType.MARKET_UPDATED,
                          EventType.ORDERBOOK_SNAPSHOT):
            snapshot = self._build_snapshot(platform, market_id, timestamp, data)

        return HistoricalReplayEvent(
            event_id=str(event_id),
            event_type=event_type,
            platform=platform,
            market_id=market_id,
            timestamp=timestamp,
            data=data,
            snapshot=snapshot,
        )

    def _build_snapshot(
        self,
        platform: str,
        market_id: str,
        timestamp: datetime,
        data: dict[str, Any],
    ) -> MarketSnapshot:
        outcomes: list[str] = list(data.get("outcomes", []))
        best_bid: dict[str, float] = dict(data.get("best_bid", {}))
        best_ask: dict[str, float] = dict(data.get("best_ask", {}))
        last_traded: dict[str, float] = dict(data.get("last_traded", {}))

        # Build orderbook levels if present
        bids: dict[str, list[OrderbookLevel]] = {}
        asks: dict[str, list[OrderbookLevel]] = {}
        for outcome, levels in data.get("bids", {}).items():
            bids[outcome] = [OrderbookLevel(**lv) if isinstance(lv, dict)
                             else OrderbookLevel(price=lv[0], size=lv[1])
                             for lv in levels]
        for outcome, levels in data.get("asks", {}).items():
            asks[outcome] = [OrderbookLevel(**lv) if isinstance(lv, dict)
                             else OrderbookLevel(price=lv[0], size=lv[1])
                             for lv in levels]

        close_time: datetime | None = None
        if data.get("close_time"):
            close_time = _parse_dt(data["close_time"])

        status_str = str(data.get("status", "active")).lower()
        try:
            status = MarketStatus(status_str)
        except ValueError:
            status = MarketStatus.ACTIVE

        return MarketSnapshot(
            platform=platform,
            market_id=market_id,
            question=str(data.get("question", "")),
            description=data.get("description"),
            outcomes=outcomes,
            best_bid=best_bid,
            best_ask=best_ask,
            last_traded=last_traded,
            bids=bids,
            asks=asks,
            fees=float(data.get("fees", 0.0)),
            status=status,
            close_time=close_time,
            snapshot_time=timestamp,
        )


# ---------------------------------------------------------------------------
# Polymarket-style adapter (example external format)
# ---------------------------------------------------------------------------


class PolymarketAdapter:
    """
    Adapts Polymarket CLOB API historical records.

    Expected raw record shape (simplified):
    {
      "id": "...",
      "condition_id": "0x...",
      "question": "...",
      "tokens": [
        {"token_id": "...", "outcome": "Yes", "price": 0.45},
        {"token_id": "...", "outcome": "No",  "price": 0.55}
      ],
      "end_date_iso": "2025-12-31T00:00:00Z",
      "update_time": 1700000000,
      "fee_rate_bps": 200
    }
    """

    PLATFORM = "polymarket"

    def adapt(self, raw: dict[str, Any]) -> HistoricalReplayEvent:
        market_id = str(raw.get("condition_id") or raw.get("id", ""))
        timestamp = _parse_dt(raw.get("update_time") or raw.get("timestamp",
                                                                  datetime.now(tz=timezone.utc)))

        tokens: list[dict[str, Any]] = raw.get("tokens", [])
        outcomes = [t["outcome"] for t in tokens if "outcome" in t]
        prices = {t["outcome"]: float(t.get("price", 0.5)) for t in tokens if "outcome" in t}

        # Synthesize bid/ask from price (Polymarket uses mid-price in feed)
        spread = 0.01
        best_bid = {o: max(0.01, p - spread / 2) for o, p in prices.items()}
        best_ask = {o: min(0.99, p + spread / 2) for o, p in prices.items()}

        close_time: datetime | None = None
        if raw.get("end_date_iso"):
            close_time = _parse_dt(raw["end_date_iso"])

        fees = float(raw.get("fee_rate_bps", 200)) / 10_000

        data = {
            "question": raw.get("question", ""),
            "outcomes": outcomes,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "last_traded": prices,
            "fees": fees,
            "close_time": close_time.isoformat() if close_time else None,
        }

        snapshot = GenericJsonAdapter()._build_snapshot(
            self.PLATFORM, market_id, timestamp, data
        )

        return HistoricalReplayEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.MARKET_UPDATED,
            platform=self.PLATFORM,
            market_id=market_id,
            timestamp=timestamp,
            data=data,
            snapshot=snapshot,
        )


# ---------------------------------------------------------------------------
# Kalshi-style adapter stub
# ---------------------------------------------------------------------------


class KalshiAdapter:
    """
    Stub adapter for Kalshi REST API records.
    Extend with real field mapping when Kalshi data is available.
    """

    PLATFORM = "kalshi"

    def adapt(self, raw: dict[str, Any]) -> HistoricalReplayEvent:
        market_id = str(raw.get("ticker") or raw.get("market_id", ""))
        timestamp = _parse_dt(raw.get("last_price_time") or raw.get("timestamp",
                                                                      datetime.now(tz=timezone.utc)))

        yes_bid = float(raw.get("yes_bid", 0.0)) / 100.0
        yes_ask = float(raw.get("yes_ask", 0.0)) / 100.0
        no_bid = 1.0 - yes_ask
        no_ask = 1.0 - yes_bid

        data = {
            "question": raw.get("title", ""),
            "outcomes": ["Yes", "No"],
            "best_bid": {"Yes": yes_bid, "No": no_bid},
            "best_ask": {"Yes": yes_ask, "No": no_ask},
            "last_traded": {
                "Yes": (yes_bid + yes_ask) / 2,
                "No": (no_bid + no_ask) / 2,
            },
            "fees": float(raw.get("fee_rate_bps", 100)) / 10_000,
            "close_time": raw.get("expiration_time"),
            "status": raw.get("status", "active"),
        }

        snapshot = GenericJsonAdapter()._build_snapshot(
            self.PLATFORM, market_id, timestamp, data
        )

        return HistoricalReplayEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.MARKET_UPDATED,
            platform=self.PLATFORM,
            market_id=market_id,
            timestamp=timestamp,
            data=data,
            snapshot=snapshot,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_ADAPTER_REGISTRY: dict[str, type] = {
    "generic": GenericJsonAdapter,
    "polymarket": PolymarketAdapter,
    "kalshi": KalshiAdapter,
}


def get_adapter(source: str) -> GenericJsonAdapter | PolymarketAdapter | KalshiAdapter:
    cls = _ADAPTER_REGISTRY.get(source.lower(), GenericJsonAdapter)
    return cls()  # type: ignore[return-value]
