"""MongoDB adapter for step 2 — reads questions, writes vectors and candidate pairs.

Collections:
    questions       — written by step 1 scraper, read + updated here
    candidate_pairs — written here, read by steps 3–7

Usage:
    adapter = MongoAdapter("mongodb://localhost:27017", database="prediction_markets")
    questions = adapter.load_questions()
    adapter.save_vectors(questions_with_vectors)
    adapter.save_candidates(candidate_pairs)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from .models import CandidatePair, MarketQuestion

log = logging.getLogger(__name__)


class MongoAdapter:
    """Read/write bridge between MongoDB and the step 2 pipeline.

    Args:
        connection_string: MongoDB URI, e.g. "mongodb://localhost:27017"
            or "mongodb+srv://user:pass@cluster.mongodb.net".
        database: Database name (default: "prediction_markets").
    """

    def __init__(self, connection_string: str, database: str = "prediction_markets") -> None:
        try:
            from pymongo import MongoClient, ASCENDING, DESCENDING
        except ImportError:
            raise ImportError("pymongo is required: pip install pymongo")

        self._client = MongoClient(connection_string)
        self._db = self._client[database]
        self._questions = self._db["questions"]
        self._candidates = self._db["candidate_pairs"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes on first connection — idempotent."""
        from pymongo import ASCENDING, DESCENDING
        # questions: fast lookup by market, fast filter for un-embedded docs
        self._questions.create_index([("market", ASCENDING)])
        self._questions.create_index([("id", ASCENDING)], unique=True)
        self._questions.create_index([("vector", ASCENDING)], sparse=True)
        # candidate_pairs: fast sort by score for frontend
        self._candidates.create_index([("similarity_score", DESCENDING)])
        self._candidates.create_index([("id", ASCENDING)], unique=True)

    # ------------------------------------------------------------------
    # Reading questions
    # ------------------------------------------------------------------

    def load_questions(self) -> List[MarketQuestion]:
        """Load all questions — with vectors if already embedded, without if not."""
        docs = list(self._questions.find({}, {"_id": 0}))
        questions = [_doc_to_question(d) for d in docs]
        log.info("Loaded %d questions from MongoDB", len(questions))
        return questions

    def load_questions_without_vectors(self) -> List[MarketQuestion]:
        """Load only questions that have not been embedded yet."""
        docs = list(self._questions.find({"vector": {"$exists": False}}, {"_id": 0}))
        questions = [_doc_to_question(d) for d in docs]
        log.info("Loaded %d un-embedded questions from MongoDB", len(questions))
        return questions

    def load_questions_with_vectors(self) -> List[MarketQuestion]:
        """Load only questions that already have a stored vector."""
        docs = list(self._questions.find({"vector": {"$exists": True}}, {"_id": 0}))
        questions = [_doc_to_question(d) for d in docs]
        log.info("Loaded %d pre-embedded questions from MongoDB", len(questions))
        return questions

    # ------------------------------------------------------------------
    # Writing vectors back to question documents
    # ------------------------------------------------------------------

    def save_vectors(self, questions: List[MarketQuestion]) -> int:
        """Write computed vectors back onto question documents.

        Only updates questions that have a non-None vector field.
        Returns the count of documents updated.
        """
        if not questions:
            return 0

        count = 0
        for q in questions:
            if q.vector is None:
                continue
            result = self._questions.update_one(
                {"id": q.id},
                {"$set": {
                    "vector": q.vector,
                    "embedded_at": datetime.now(timezone.utc),
                }},
            )
            count += result.modified_count

        log.info("Saved vectors for %d questions", count)
        return count

    # ------------------------------------------------------------------
    # Writing candidate pairs
    # ------------------------------------------------------------------

    def save_candidates(self, candidates: List[CandidatePair]) -> int:
        """Upsert candidate pairs into MongoDB.

        Uses the deterministic pair ID so re-runs don't create duplicates.
        Returns the count of pairs written.
        """
        if not candidates:
            return 0

        count = 0
        for pair in candidates:
            doc = _pair_to_doc(pair)
            result = self._candidates.update_one(
                {"id": pair.id},
                {"$set": doc},
                upsert=True,
            )
            count += (1 if result.upserted_id is not None else result.modified_count)

        log.info("Saved %d candidate pairs to MongoDB", count)
        return count

    # ------------------------------------------------------------------
    # Reading candidates (for frontend / downstream steps)
    # ------------------------------------------------------------------

    def load_candidates(
        self,
        min_score: float = 0.70,
        limit: int = 200,
    ) -> List[dict]:
        """Load candidate pairs sorted by similarity score for the frontend.

        Returns raw dicts so any consumer can use them without importing
        our dataclasses.
        """
        docs = list(
            self._candidates
            .find({"similarity_score": {"$gte": min_score}}, {"_id": 0})
            .sort("similarity_score", -1)
            .limit(limit)
        )
        log.info("Loaded %d candidate pairs (min_score=%.2f)", len(docs), min_score)
        return docs

    def count_questions(self) -> dict:
        """Return question counts per market — useful for pipeline status."""
        pipeline = [{"$group": {"_id": "$market", "count": {"$sum": 1}}}]
        return {d["_id"]: d["count"] for d in self._questions.aggregate(pipeline)}

    def close(self) -> None:
        self._client.close()


# ------------------------------------------------------------------
# Private conversion helpers
# ------------------------------------------------------------------

def _doc_to_question(doc: dict) -> MarketQuestion:
    """Convert a MongoDB document to a MarketQuestion dataclass."""
    return MarketQuestion(
        id=doc["id"],
        text=doc["text"],
        market=doc["market"],
        price=float(doc.get("price", 0.5)),
        metadata={k: v for k, v in doc.items()
                  if k not in ("id", "text", "market", "price", "vector", "embedded_at", "created_at")},
        vector=doc.get("vector"),  # None if not yet embedded
    )


def _pair_to_doc(pair: CandidatePair) -> dict:
    """Convert a CandidatePair dataclass to a MongoDB document."""
    price_spread = abs(pair.question_a.price - pair.question_b.price)
    return {
        "id": pair.id,
        "question_id_a": pair.question_a.id,
        "question_id_b": pair.question_b.id,
        "text_a": pair.question_a.text,
        "text_b": pair.question_b.text,
        "market_a": pair.question_a.market,
        "market_b": pair.question_b.market,
        "price_a": pair.question_a.price,
        "price_b": pair.question_b.price,
        "price_spread": round(price_spread, 4),
        "similarity_score": round(pair.similarity_score, 4),
        "has_potential_negation": pair.has_potential_negation,
        "negation_tokens": pair.negation_tokens,
        "created_at": datetime.now(timezone.utc),
    }
