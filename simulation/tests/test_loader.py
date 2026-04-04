"""Tests for data loading and adapters."""

import json
import tempfile
from pathlib import Path

import pytest

from simulation.data.adapters import GenericJsonAdapter, PolymarketAdapter, get_adapter
from simulation.data.loader import HistoricalDataLoader, load_toy_dataset
from simulation.models import EventType, MarketStatus


class TestGenericJsonAdapter:
    def test_adapt_market_updated(self) -> None:
        raw = {
            "event_type": "market_updated",
            "platform": "polymarket",
            "market_id": "abc123",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {
                "question": "Will X happen?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": 0.44, "No": 0.54},
                "best_ask": {"Yes": 0.46, "No": 0.56},
                "last_traded": {"Yes": 0.45, "No": 0.55},
                "fees": 0.02,
            },
        }
        adapter = GenericJsonAdapter()
        event = adapter.adapt(raw)
        assert event.platform == "polymarket"
        assert event.market_id == "abc123"
        assert event.event_type == EventType.MARKET_UPDATED
        assert event.snapshot is not None
        assert event.snapshot.question == "Will X happen?"
        assert event.snapshot.best_bid["Yes"] == 0.44

    def test_adapt_market_resolved(self) -> None:
        raw = {
            "event_type": "market_resolved",
            "platform": "kalshi",
            "market_id": "m1",
            "timestamp": "2024-12-31T23:00:00Z",
            "data": {"resolution_outcome": "Yes", "resolution_value": 1.0},
        }
        adapter = GenericJsonAdapter()
        event = adapter.adapt(raw)
        assert event.event_type == EventType.MARKET_RESOLVED
        assert event.data["resolution_outcome"] == "Yes"
        assert event.snapshot is None  # no snapshot for resolved events

    def test_adapt_unknown_event_type_defaults(self) -> None:
        raw = {
            "event_type": "something_weird",
            "platform": "x",
            "market_id": "y",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {},
        }
        event = GenericJsonAdapter().adapt(raw)
        assert event.event_type == EventType.MARKET_UPDATED

    def test_snapshot_status_defaults_active(self) -> None:
        raw = {
            "event_type": "market_created",
            "platform": "p",
            "market_id": "m",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {
                "question": "Q?",
                "outcomes": ["Yes", "No"],
                "best_bid": {},
                "best_ask": {},
                "last_traded": {},
            },
        }
        event = GenericJsonAdapter().adapt(raw)
        assert event.snapshot is not None
        assert event.snapshot.status == MarketStatus.ACTIVE


class TestPolymarketAdapter:
    def test_adapt_polymarket_record(self) -> None:
        raw = {
            "condition_id": "0xabc",
            "question": "Will BTC hit $100k?",
            "tokens": [
                {"outcome": "Yes", "price": 0.45},
                {"outcome": "No", "price": 0.55},
            ],
            "update_time": 1704067200,
            "fee_rate_bps": 200,
            "end_date_iso": "2024-12-31T00:00:00Z",
        }
        adapter = PolymarketAdapter()
        event = adapter.adapt(raw)
        assert event.platform == "polymarket"
        assert event.market_id == "0xabc"
        assert event.snapshot is not None
        assert event.snapshot.last_traded["Yes"] == 0.45


class TestLoader:
    def test_load_from_records(self) -> None:
        records = [
            {
                "event_type": "market_updated",
                "platform": "poly",
                "market_id": "m1",
                "timestamp": "2024-01-01T00:00:00Z",
                "data": {
                    "question": "Q?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {"Yes": 0.44},
                    "best_ask": {"Yes": 0.46},
                    "last_traded": {"Yes": 0.45},
                },
            }
        ]
        loader = HistoricalDataLoader("")
        events = list(loader.load_from_records(records))
        assert len(events) == 1
        assert events[0].market_id == "m1"

    def test_load_from_json_file(self) -> None:
        records = [
            {
                "event_type": "market_created",
                "platform": "x",
                "market_id": "m1",
                "timestamp": "2024-01-01T00:00:00Z",
                "data": {
                    "question": "Q?",
                    "outcomes": ["Yes", "No"],
                    "best_bid": {},
                    "best_ask": {},
                    "last_traded": {},
                },
            }
        ]
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(records, f)
            fpath = f.name

        loader = HistoricalDataLoader(fpath)
        events = list(loader.load())
        assert len(events) == 1

    def test_load_from_jsonl_file(self) -> None:
        record = {
            "event_type": "market_updated",
            "platform": "x",
            "market_id": "m2",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {"question": "Q?", "outcomes": [], "best_bid": {}, "best_ask": {}, "last_traded": {}},
        }
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write(json.dumps(record) + "\n")
            fpath = f.name

        loader = HistoricalDataLoader(fpath)
        events = list(loader.load())
        assert len(events) == 1

    def test_load_nonexistent_path_yields_nothing(self) -> None:
        loader = HistoricalDataLoader("/nonexistent/path/abc123")
        events = list(loader.load())
        assert events == []

    def test_toy_dataset_loads(self) -> None:
        events = load_toy_dataset()
        assert len(events) >= 5
        types = {e.event_type for e in events}
        assert EventType.MARKET_CREATED in types
        assert EventType.MARKET_RESOLVED in types

    def test_get_adapter_registry(self) -> None:
        assert isinstance(get_adapter("generic"), GenericJsonAdapter)
        assert isinstance(get_adapter("polymarket"), PolymarketAdapter)
        assert isinstance(get_adapter("unknown"), GenericJsonAdapter)
