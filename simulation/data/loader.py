"""
Historical data loader.

Reads historical market records from disk (JSON / CSV / JSONL) and
converts them into normalized HistoricalReplayEvent streams.

Supports:
  - .json  — list of records or single record
  - .jsonl — newline-delimited JSON
  - .csv   — tabular with 'event_type', 'platform', 'market_id', 'timestamp', 'data_json'

The loader yields events unsorted; the ReplayStream handles ordering.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
from typing import Generator

from simulation.data.adapters import GenericJsonAdapter, get_adapter
from simulation.models import HistoricalReplayEvent

logger = logging.getLogger(__name__)


class HistoricalDataLoader:
    """
    Loads and normalizes historical replay events from disk.

    Usage:
        loader = HistoricalDataLoader("path/to/data/dir")
        events = list(loader.load())
    """

    def __init__(self, data_path: str, adapter_source: str = "generic") -> None:
        self.data_path = Path(data_path)
        self._adapter = get_adapter(adapter_source)

    def load(self) -> Generator[HistoricalReplayEvent, None, None]:
        """
        Recursively yield all events from the data path.
        Handles files and directories.
        """
        path = self.data_path
        if not path.exists():
            logger.warning("Data path does not exist: %s", path)
            return

        if path.is_file():
            yield from self._load_file(path)
        elif path.is_dir():
            for root, _dirs, files in os.walk(path):
                for fname in sorted(files):
                    fpath = Path(root) / fname
                    if fpath.suffix in (".json", ".jsonl", ".csv"):
                        yield from self._load_file(fpath)

    def load_from_records(
        self, records: list[dict], adapter_source: str = "generic"
    ) -> Generator[HistoricalReplayEvent, None, None]:
        """
        Load directly from a list of raw dicts (useful for tests and inline fixtures).
        """
        adapter = get_adapter(adapter_source)
        for raw in records:
            try:
                yield adapter.adapt(raw)
            except Exception:
                logger.exception("Failed to adapt record: %s", raw)

    # ------------------------------------------------------------------

    def _load_file(self, path: Path) -> Generator[HistoricalReplayEvent, None, None]:
        logger.debug("Loading: %s", path)
        try:
            if path.suffix == ".jsonl":
                yield from self._load_jsonl(path)
            elif path.suffix == ".json":
                yield from self._load_json(path)
            elif path.suffix == ".csv":
                yield from self._load_csv(path)
        except Exception:
            logger.exception("Failed to load file: %s", path)

    def _load_json(self, path: Path) -> Generator[HistoricalReplayEvent, None, None]:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        records = payload if isinstance(payload, list) else [payload]
        for raw in records:
            try:
                yield self._adapter.adapt(raw)
            except Exception:
                logger.exception("Skipping malformed record in %s", path)

    def _load_jsonl(self, path: Path) -> Generator[HistoricalReplayEvent, None, None]:
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    yield self._adapter.adapt(raw)
                except json.JSONDecodeError:
                    logger.warning("Bad JSON on line %d of %s", lineno, path)
                except Exception:
                    logger.exception("Skipping record on line %d of %s", lineno, path)

    def _load_csv(self, path: Path) -> Generator[HistoricalReplayEvent, None, None]:
        """
        Expected CSV columns:
          event_type, platform, market_id, timestamp, data_json
        where data_json is the JSON-encoded data payload.
        """
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    raw: dict = {
                        "event_type": row.get("event_type", "market_updated"),
                        "platform": row.get("platform", "unknown"),
                        "market_id": row.get("market_id", ""),
                        "timestamp": row.get("timestamp", ""),
                        "data": json.loads(row.get("data_json", "{}")),
                    }
                    yield self._adapter.adapt(raw)
                except Exception:
                    logger.exception("Skipping malformed CSV row: %s", row)


def load_toy_dataset() -> list[HistoricalReplayEvent]:
    """
    Return a small built-in toy dataset for smoke tests and demos.
    Simulates a simple Bitcoin price arbitrage scenario.
    """
    from datetime import timezone

    records = [
        # T=0: both markets created
        {
            "event_type": "market_created",
            "platform": "polymarket",
            "market_id": "poly_btc_100k",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {
                "question": "Will Bitcoin reach $100,000 by Dec 31, 2024?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": 0.44, "No": 0.52},
                "best_ask": {"Yes": 0.46, "No": 0.54},
                "last_traded": {"Yes": 0.45, "No": 0.55},
                "fees": 0.02,
                "close_time": "2024-12-31T23:59:59Z",
            },
        },
        {
            "event_type": "market_created",
            "platform": "kalshi",
            "market_id": "kalshi_btc_100k",
            "timestamp": "2024-01-01T00:05:00Z",
            "data": {
                "question": "Bitcoin above $100,000 before Jan 1, 2025?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": 0.40, "No": 0.56},
                "best_ask": {"Yes": 0.42, "No": 0.58},
                "last_traded": {"Yes": 0.41, "No": 0.59},
                "fees": 0.02,
                "close_time": "2024-12-31T23:59:59Z",
            },
        },
        # T=1: arb opportunity opens — prices diverge
        {
            "event_type": "market_updated",
            "platform": "polymarket",
            "market_id": "poly_btc_100k",
            "timestamp": "2024-01-02T10:00:00Z",
            "data": {
                "question": "Will Bitcoin reach $100,000 by Dec 31, 2024?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": 0.38, "No": 0.58},
                "best_ask": {"Yes": 0.40, "No": 0.60},
                "last_traded": {"Yes": 0.39, "No": 0.59},
                "fees": 0.02,
                "close_time": "2024-12-31T23:59:59Z",
            },
        },
        {
            "event_type": "market_updated",
            "platform": "kalshi",
            "market_id": "kalshi_btc_100k",
            "timestamp": "2024-01-02T10:01:00Z",
            "data": {
                "question": "Bitcoin above $100,000 before Jan 1, 2025?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": 0.55, "No": 0.43},
                "best_ask": {"Yes": 0.57, "No": 0.45},
                "last_traded": {"Yes": 0.56, "No": 0.44},
                "fees": 0.02,
                "close_time": "2024-12-31T23:59:59Z",
            },
        },
        # T=2: prices converge back to fair
        {
            "event_type": "market_updated",
            "platform": "polymarket",
            "market_id": "poly_btc_100k",
            "timestamp": "2024-06-01T00:00:00Z",
            "data": {
                "question": "Will Bitcoin reach $100,000 by Dec 31, 2024?",
                "outcomes": ["Yes", "No"],
                "best_bid": {"Yes": 0.58, "No": 0.40},
                "best_ask": {"Yes": 0.60, "No": 0.42},
                "last_traded": {"Yes": 0.59, "No": 0.41},
                "fees": 0.02,
                "close_time": "2024-12-31T23:59:59Z",
            },
        },
        # T=3: resolution — Yes wins on both platforms
        {
            "event_type": "market_resolved",
            "platform": "polymarket",
            "market_id": "poly_btc_100k",
            "timestamp": "2025-01-01T00:10:00Z",
            "data": {
                "resolution_outcome": "Yes",
                "resolution_value": 1.0,
            },
        },
        {
            "event_type": "market_resolved",
            "platform": "kalshi",
            "market_id": "kalshi_btc_100k",
            "timestamp": "2025-01-01T00:10:00Z",
            "data": {
                "resolution_outcome": "Yes",
                "resolution_value": 1.0,
            },
        },
    ]

    loader = HistoricalDataLoader("")
    return list(loader.load_from_records(records))
