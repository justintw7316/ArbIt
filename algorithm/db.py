"""Shared MongoDB helpers used by Phases 4 and 5."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

if TYPE_CHECKING:
    from pymongo.database import Database

# Collection names
PRICE_HISTORY_COL = "price_history"
SIGNALS_COL = "signals"
VALIDATED_COL = "validated_opportunities"
MARKETS_COL = "markets"

_SYSTEM_DBS = {"admin", "local", "config"}
_PREFERRED_DBS = ["prediction_markets", "Arbit", "arbit", "arbsignal"]

_client: MongoClient | None = None
_db_name: str | None = None


def _discover_db_name(client: "MongoClient") -> str:
    """Discover DB name from env vars or by listing available databases."""
    name = os.getenv("MONGO_DB") or os.getenv("MONGO_DATABASE")
    if name:
        return name
    try:
        available = set(client.list_database_names())
        for preferred in _PREFERRED_DBS:
            if preferred in available:
                return preferred
        for n in available:
            if n not in _SYSTEM_DBS:
                return n
    except Exception:
        pass
    return "prediction_markets"


def get_mongo_uri() -> str:
    """Return the MongoDB URI (DATABASE_URL takes priority over MONGO_URI)."""
    return os.getenv("DATABASE_URL") or os.getenv("MONGO_URI", "mongodb://localhost:27017")


def get_db_name() -> str:
    """Return the resolved database name (connects if needed)."""
    get_db()
    return _db_name  # type: ignore[return-value]


def get_db() -> "Database":
    global _client, _db_name
    if _client is None:
        _client = MongoClient(get_mongo_uri())
    if _db_name is None:
        _db_name = _discover_db_name(_client)
    return _client[_db_name]


def reset_client() -> None:
    """Reset the client (useful in tests)."""
    global _client, _db_name
    _client = None
    _db_name = None
