"""ARBX FastAPI backend — serves arbitrage data from MongoDB to the frontend."""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient, DESCENDING

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from simulation.run_backtest import run_backtest
    from simulation.analytics.reports import summary_dict
    from simulation.config import SimulationConfig
    from simulation.models import RealismMode as SimRealismMode
    _SIM_AVAILABLE = True
except ImportError:
    _SIM_AVAILABLE = False

load_dotenv()

MONGO_URI = os.getenv("DATABASE_URL") or os.getenv("MONGO_URI", "mongodb://localhost:27017")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.70"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-mpnet-base-v2")

_SYSTEM_DBS = {"admin", "local", "config"}
_PREFERRED_DBS = ["arbsignal", "Arbit", "arbit", "prediction_markets"]

app = FastAPI(title="ARBX API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_client: Optional[MongoClient] = None
_db_name: Optional[str] = None


def _discover_db_name(client: MongoClient) -> str:
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


def get_db():
    global _client, _db_name
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    if _db_name is None:
        _db_name = _discover_db_name(_client)
    return _client[_db_name]


def db_status() -> str:
    try:
        get_db().command("ping")
        return "connected"
    except Exception:
        return "error"


_STOPWORDS: Set[str] = {
    "will", "the", "a", "an", "to", "of", "in", "by", "for", "on", "at", "or", "be", "is", "are",
    "was", "were", "been", "being", "have", "has", "had", "do", "does", "did", "not", "no", "yes",
    "before", "after", "end", "year", "than", "from", "with", "into", "any", "all", "can", "may",
    "this", "that", "these", "those", "and", "but", "if", "when", "how", "what", "who", "which",
}


def _signal_word_set(text_a: str, text_b: str) -> Set[str]:
    """Token set for diversity (cheap proxy for topic overlap)."""
    combined = f"{text_a or ''} {text_b or ''}"
    words = re.findall(r"[a-z0-9]+", combined.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _diversify_signals_mmr(
    docs: List[Dict[str, Any]],
    limit: int,
    diversity_lambda: float,
) -> List[Dict[str, Any]]:
    """Greedy MMR: balance expected_profit with dissimilarity to already-picked rows."""
    if not docs or limit <= 0:
        return []
    n = len(docs)
    evs = [float(d.get("expected_profit") or 0) for d in docs]
    max_ev = max(evs) if evs else 1.0
    if max_ev <= 0:
        max_ev = 1.0
    ev_norm = [e / max_ev for e in evs]
    word_sets = [
        _signal_word_set(str(d.get("text_a") or ""), str(d.get("text_b") or ""))
        or {str(d.get("pair_id") or f"idx{i}")}
        for i, d in enumerate(docs)
    ]

    selected: List[int] = [0]
    remaining = set(range(1, n))

    while len(selected) < limit and remaining:
        best_i: Optional[int] = None
        best_score = -1e18
        for i in remaining:
            redundancy = max(_jaccard(word_sets[i], word_sets[j]) for j in selected)
            mmr = diversity_lambda * ev_norm[i] - (1.0 - diversity_lambda) * redundancy
            if mmr > best_score:
                best_score = mmr
                best_i = i
        if best_i is None:
            break
        selected.append(best_i)
        remaining.discard(best_i)

    return [docs[i] for i in selected]


# ── Candidates (Phase 2) ──────────────────────────────────────────────────────

@app.get("/api/candidates")
def get_candidates(
    min_score: float = Query(default=0.70, ge=0.0, le=1.0),
    limit: int = Query(default=200, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    try:
        db = get_db()
        docs = list(
            db["candidate_pairs"]
            .find({"similarity_score": {"$gte": min_score}}, {"_id": 0})
            .sort("similarity_score", DESCENDING)
            .limit(limit)
        )
        for doc in docs:
            if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
                doc["created_at"] = doc["created_at"].isoformat()
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


# ── Signals (Phase 4) ─────────────────────────────────────────────────────────

@app.get("/api/signals")
def get_signals(
    min_ev: float = Query(default=0.0),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=200, ge=1, le=1000),
    ranking: str = Query(
        default="profit",
        description="profit = pure EV order; diverse = MMR portfolio mix (topic spread)",
    ),
    diversity_lambda: float = Query(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Higher = weight EV more vs diversity (only when ranking=diverse)",
    ),
    pool_multiplier: int = Query(
        default=6,
        ge=2,
        le=25,
        description="Fetch up to limit×this many candidates before diversifying",
    ),
) -> List[Dict[str, Any]]:
    try:
        db = get_db()
        query: Dict[str, Any] = {}
        if min_ev > 0:
            query["expected_profit"] = {"$gte": min_ev}
        if min_confidence > 0:
            query["confidence"] = {"$gte": min_confidence}

        use_diverse = ranking.strip().lower() == "diverse"
        fetch_cap = min(1000, limit * pool_multiplier) if use_diverse else limit

        docs = list(
            db["signals"]
            .find(query, {"_id": 0})
            .sort("expected_profit", DESCENDING)
            .limit(fetch_cap)
        )
        # Enrich with question text from candidate_pairs
        pair_ids = [d["pair_id"] for d in docs if "pair_id" in d]
        if pair_ids:
            pairs = {
                p["id"]: p
                for p in db["candidate_pairs"].find(
                    {"id": {"$in": pair_ids}},
                    {"_id": 0, "id": 1, "text_a": 1, "text_b": 1},
                )
            }
            for doc in docs:
                p = pairs.get(doc.get("pair_id"), {})
                doc["text_a"] = p.get("text_a", "")
                doc["text_b"] = p.get("text_b", "")
        if use_diverse and docs:
            docs = _diversify_signals_mmr(docs, limit=limit, diversity_lambda=diversity_lambda)
        elif len(docs) > limit:
            docs = docs[:limit]
        # Normalise datetime fields and enums
        for doc in docs:
            for k in ("created_at", "generated_at"):
                if k in doc and hasattr(doc[k], "isoformat"):
                    doc[k] = doc[k].isoformat()
            for k in ("platform_a", "platform_b"):
                if k in doc and not isinstance(doc[k], str):
                    doc[k] = str(doc[k])
            if "direction" in doc and not isinstance(doc["direction"], str):
                doc["direction"] = str(doc["direction"])
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.get("/api/signals/stats")
def get_signals_stats() -> Dict[str, Any]:
    try:
        db = get_db()
        col = db["signals"]
        total = col.count_documents({})
        if total == 0:
            return {"total": 0, "total_ev": 0, "top_ev": 0, "avg_confidence": 0, "avg_spread": 0}

        pipeline = [
            {"$group": {
                "_id": None,
                "total_ev":       {"$sum": "$expected_profit"},
                "top_ev":         {"$max": "$expected_profit"},
                "avg_confidence": {"$avg": "$confidence"},
                "avg_spread":     {"$avg": "$raw_spread"},
            }}
        ]
        agg = list(col.aggregate(pipeline))
        stats = agg[0] if agg else {}
        return {
            "total":           total,
            "total_ev":        round(stats.get("total_ev", 0), 2),
            "top_ev":          round(stats.get("top_ev", 0), 2),
            "avg_confidence":  round(stats.get("avg_confidence", 0), 4),
            "avg_spread":      round(stats.get("avg_spread", 0), 4),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


# ── Validated opportunities (Phase 5) ────────────────────────────────────────

@app.get("/api/validated")
def get_validated(
    executable_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> List[Dict[str, Any]]:
    try:
        db = get_db()
        query: Dict[str, Any] = {}
        if executable_only:
            query["executable"] = True
        docs = list(
            db["validated_opportunities"]
            .find(query, {"_id": 0})
            .sort("signal.expected_profit", DESCENDING)
            .limit(limit)
        )
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


# ── Questions ─────────────────────────────────────────────────────────────────

@app.get("/api/questions")
def get_questions(market: Optional[str] = Query(default=None)) -> List[Dict[str, Any]]:
    try:
        db = get_db()
        query = {"platform": market} if market else {}
        projection = {"_id": 0, "market_id": 1, "question": 1, "platform": 1, "yes_price": 1}
        docs = list(db["markets"].find(query, projection).limit(200))
        # Normalise to frontend expected field names
        return [
            {"id": d.get("market_id", ""), "text": d.get("question", ""),
             "market": d.get("platform", ""), "price": d.get("yes_price", 0.5)}
            for d in docs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


# ── Pipeline status ───────────────────────────────────────────────────────────

@app.get("/api/pipeline-status")
def get_pipeline_status() -> Dict[str, Any]:
    STEPS = [
        (1, "SCRAPE",    "Market Scraper"),
        (2, "VECTOR DB", "Embedding & Vector DB"),
        (3, "LLM VERIFY","LLM Verifier"),
        (4, "ARB CALC",  "Arbitrage Calculator"),
        (5, "TIMING",    "Timing Localizer"),
        (6, "SIM",       "Simulator"),
        (7, "DISP",      "Display"),
    ]
    try:
        db = get_db()
        # Derive live counts from actual collections
        try:
            n_candidates = db["candidate_pairs"].count_documents({})
            n_signals    = db["signals"].count_documents({})
            n_validated  = db["validated_opportunities"].count_documents({})
            n_executable = db["validated_opportunities"].count_documents({"executable": True})
        except Exception:
            n_candidates = n_signals = n_validated = n_executable = 0

        steps = [
            {"number": 1, "short_label": "SCRAPE",    "full_label": "Market Scraper",         "status": "done"    if n_candidates > 0 else "pending", "elapsed_ms": None, "message": None},
            {"number": 2, "short_label": "VECTOR DB", "full_label": "Embedding & Vector DB",  "status": "done"    if n_candidates > 0 else "pending", "elapsed_ms": None, "message": f"{n_candidates} candidate pairs"},
            {"number": 3, "short_label": "LLM VERIFY","full_label": "LLM Verifier",           "status": "done"    if n_signals > 0    else "pending", "elapsed_ms": None, "message": None},
            {"number": 4, "short_label": "ARB CALC",  "full_label": "Arbitrage Calculator",   "status": "done"    if n_signals > 0    else "pending", "elapsed_ms": None, "message": f"{n_signals} signals"},
            {"number": 5, "short_label": "VALIDATE",  "full_label": "Live Validator",         "status": "done"    if n_validated > 0  else "pending", "elapsed_ms": None, "message": f"{n_executable} executable"},
            {"number": 6, "short_label": "SIM",       "full_label": "Simulator",              "status": "pending", "elapsed_ms": None, "message": None},
            {"number": 7, "short_label": "DISP",      "full_label": "Display",                "status": "pending", "elapsed_ms": None, "message": None},
        ]
        return {"last_run": None, "total_runtime_ms": 0, "steps": steps, "logs": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


# ── Simulation (historical backtest) ─────────────────────────────────────────

def _price_to_resolution(doc: Dict[str, Any]) -> Optional[str]:
    """Derive YES/NO resolution from most-recent price_history entry or current yes_price.

    price_history ordering differs by platform (Kalshi=ASC oldest→newest,
    Manifold=DESC newest→oldest), so we pick the entry with the largest timestamp.
    """
    ph = doc.get("price_history") or []
    if ph:
        # Pick the entry with the highest timestamp regardless of array order
        most_recent = max(ph, key=lambda p: p.get("timestamp", 0))
        last_price = most_recent.get("yes_price")
    else:
        last_price = doc.get("yes_price")
    if last_price is None:
        return None
    if last_price >= 0.8:
        return "YES"
    if last_price <= 0.2:
        return "NO"
    return None


_SIM_ENTRY_LOOKBACK = 30  # days before market expiry to "discover" the opportunity


def _build_simulation_trades(db, as_of_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Core logic: build enriched trade list for backtest simulation (single batched query)."""
    signals = list(db["signals"].find({}, {"_id": 0}))

    # Collect all referenced market ids
    market_ids: set = set()
    for s in signals:
        market_ids.add(s.get("market_a_id", ""))
        market_ids.add(s.get("market_b_id", ""))
    market_ids.discard("")

    # Single batched fetch for all markets (end_date + last price snapshot)
    markets = {
        d["market_id"]: d
        for d in db["markets"].find(
            {"market_id": {"$in": list(market_ids)}},
            # Fetch last 2 entries so _price_to_resolution can check the most-recent price.
            # price_history order varies by platform (Kalshi=ASC, Manifold=DESC), so we
            # sort explicitly in _price_to_resolution instead of relying on array order.
            {"market_id": 1, "end_date": 1, "price_history": {"$slice": -2}, "yes_price": 1, "platform": 1, "_id": 0},
        )
    }

    # Enrich signals with question text from candidate_pairs
    pair_ids = [s.get("pair_id") for s in signals if s.get("pair_id")]
    pairs = {
        p["id"]: p
        for p in db["candidate_pairs"].find(
            {"id": {"$in": pair_ids}},
            {"_id": 0, "id": 1, "text_a": 1, "text_b": 1},
        )
    }

    backtest_start = (_date.today() - timedelta(days=365)).isoformat()
    trades: List[Dict[str, Any]] = []

    for sig in signals:
        ma = markets.get(sig.get("market_a_id", ""), {})
        mb = markets.get(sig.get("market_b_id", ""), {})
        pair = pairs.get(sig.get("pair_id", ""), {})

        end_a = ma.get("end_date")
        end_b = mb.get("end_date")
        end_date_a = str(end_a or "")[:10] or None
        end_date_b = str(end_b or "")[:10] or None
        exit_date = str(end_a or end_b or "")[:10]

        # Resolve from batched market data (no extra round-trips)
        res_a = _price_to_resolution(ma) if ma else None
        res_b = _price_to_resolution(mb) if mb else None

        # Realized P&L
        price_a = float(sig.get("price_a", 0.5))
        price_b = float(sig.get("price_b", 0.5))
        direction = sig.get("direction", "")
        size = float(sig.get("recommended_size_usd", 100))
        raw_spread = float(sig.get("raw_spread", 0))
        realized_pnl = None
        outcome = "UNKNOWN"

        if res_a and res_b:
            if res_a == res_b:
                outcome = "WIN"
                realized_pnl = round(raw_spread * size, 2)
            else:
                if direction == "buy_b_sell_a":
                    pnl_b = (1.0 - price_b) if res_b == "YES" else -price_b
                    pnl_a = price_a if res_a == "NO" else -(1.0 - price_a)
                else:
                    pnl_a = (1.0 - price_a) if res_a == "YES" else -price_a
                    pnl_b = price_b if res_b == "NO" else -(1.0 - price_b)
                realized_pnl = round((pnl_a + pnl_b) * size, 2)
                outcome = "WIN" if realized_pnl >= 0 else "LOSS"

        # Normalise datetimes/enums
        for k in ("created_at", "generated_at"):
            if k in sig and hasattr(sig[k], "isoformat"):
                sig[k] = sig[k].isoformat()
        for k in ("platform_a", "platform_b", "direction"):
            if k in sig and not isinstance(sig[k], str):
                sig[k] = str(sig[k])

        # entry_date: discovered ENTRY_LOOKBACK days before expiry
        if exit_date:
            try:
                entry_date = (_date.fromisoformat(exit_date) - timedelta(days=_SIM_ENTRY_LOOKBACK)).isoformat()
            except ValueError:
                entry_date = backtest_start
        else:
            entry_date = backtest_start

        trades.append({
            **sig,
            "text_a": pair.get("text_a", ""),
            "text_b": pair.get("text_b", ""),
            "exit_date": exit_date,
            "entry_date": entry_date,
            "end_date_a": end_date_a,
            "end_date_b": end_date_b,
            "resolution_a": res_a,
            "resolution_b": res_b,
            "outcome": outcome,
            "realized_pnl": realized_pnl,
        })

    if as_of_date:
        trades = [
            t for t in trades
            if (t.get("end_date_a") or "9999") >= as_of_date
            and (t.get("end_date_b") or "9999") >= as_of_date
        ]

    trades.sort(key=lambda t: t.get("exit_date") or "")
    return trades


@app.get("/api/simulation/trades")
def get_simulation_trades(
    as_of_date: Optional[str] = Query(default=None, description="ISO date (YYYY-MM-DD); only show trades where both markets were still open on this date"),
) -> List[Dict[str, Any]]:
    """Return all signals enriched with resolution outcomes for backtesting."""
    try:
        return _build_simulation_trades(get_db(), as_of_date=as_of_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.get("/api/simulation/pnl-curve")
def get_simulation_pnl_curve() -> List[Dict[str, Any]]:
    """Return a continuous 365-day cumulative P&L curve from backtest start to today."""
    try:
        from collections import defaultdict
        db = get_db()
        trades = _build_simulation_trades(db)
        daily: Dict[str, float] = defaultdict(float)
        backtest_start = _date.today() - timedelta(days=365)
        backtest_start_s = backtest_start.isoformat()
        for t in trades:
            exit_d = t.get("exit_date", "")
            pnl = t.get("realized_pnl") or 0.0
            if exit_d:
                # Clamp pre-backtest resolutions onto day 1
                eff_date = exit_d if exit_d >= backtest_start_s else backtest_start_s
                daily[eff_date] += pnl

        # Generate continuous daily range (one point per calendar day)
        cumulative = 0.0
        curve = []
        d = backtest_start
        today = _date.today()
        while d <= today:
            ds = d.isoformat()
            day_pnl = daily.get(ds, 0.0)
            cumulative += day_pnl
            curve.append({"date": ds, "daily_pnl": round(day_pnl, 2), "cumulative_pnl": round(cumulative, 2)})
            d += timedelta(days=1)
        return curve
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


# ── Simulation run (POST) ─────────────────────────────────────────────────────

class SimRunRequest(BaseModel):
    realism_mode: str = "realistic"
    initial_capital: float = 10000.0


@app.post("/api/simulation/run")
def run_simulation(req: SimRunRequest) -> Dict[str, Any]:
    """Run a full backtest simulation and return summary + equity curve + trade log."""
    if not _SIM_AVAILABLE:
        raise HTTPException(status_code=501, detail={"error": "Simulation module not available"})
    try:
        mode = SimRealismMode(req.realism_mode)
        cfg = SimulationConfig(realism_mode=mode, initial_capital=req.initial_capital)
        result = run_backtest(cfg)
        return summary_dict(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config")
def get_config() -> Dict[str, Any]:
    return {
        "embedding_model": EMBEDDING_MODEL,
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "db_status": db_status(),
        "markets": ["polymarket", "kalshi", "manifold"],
        "last_run": None,
    }
