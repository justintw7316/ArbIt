"""Tests for MongoAdapter using mongomock (no live MongoDB required)."""

import pytest
import mongomock

from vector_db.models import CandidatePair, MarketQuestion
from vector_db.mongo_adapter import MongoAdapter, _doc_to_question, _pair_to_doc


# ---------------------------------------------------------------------------
# Fixture: adapter backed by an in-memory mongomock client
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    """MongoAdapter wired to an in-memory mongomock database."""
    client = mongomock.MongoClient()
    db = client["test_db"]
    a = MongoAdapter.__new__(MongoAdapter)
    a._client = client
    a._db = db
    a._questions = db["questions"]
    a._candidates = db["candidate_pairs"]
    return a


def _q(id: str, text: str, market: str, price: float = 0.5, vector=None) -> dict:
    """Raw MongoDB question document (as step 1 would insert it)."""
    doc = {"id": id, "text": text, "market": market, "price": price}
    if vector is not None:
        doc["vector"] = vector
    return doc


def _mq(id: str, text: str, market: str, price: float = 0.5) -> MarketQuestion:
    return MarketQuestion(id=id, text=text, market=market, price=price)


# ---------------------------------------------------------------------------
# _doc_to_question conversion
# ---------------------------------------------------------------------------

class TestDocToQuestion:
    def test_basic_fields(self):
        doc = {"id": "pm1", "text": "Will BTC hit 100k?", "market": "polymarket", "price": 0.41}
        q = _doc_to_question(doc)
        assert q.id == "pm1"
        assert q.text == "Will BTC hit 100k?"
        assert q.market == "polymarket"
        assert q.price == 0.41
        assert q.vector is None

    def test_vector_loaded(self):
        vec = [0.1, 0.2, 0.3]
        doc = {"id": "pm1", "text": "text", "market": "polymarket", "price": 0.5, "vector": vec}
        q = _doc_to_question(doc)
        assert q.vector == vec

    def test_extra_fields_go_to_metadata(self):
        doc = {"id": "pm1", "text": "text", "market": "polymarket",
               "price": 0.5, "volume": 1000, "close_time": "2025-12-31"}
        q = _doc_to_question(doc)
        assert q.metadata["volume"] == 1000
        assert q.metadata["close_time"] == "2025-12-31"


# ---------------------------------------------------------------------------
# load_questions_without_vectors
# ---------------------------------------------------------------------------

class TestLoadQuestionsWithoutVectors:
    def test_returns_only_unembedded(self, adapter):
        adapter._questions.insert_many([
            _q("pm1", "BTC 100k?", "polymarket"),                          # no vector
            _q("kl1", "BTC surpasses 100k?", "kalshi", vector=[0.1, 0.2]), # has vector
            _q("pm2", "ETH 10k?", "polymarket"),                           # no vector
        ])
        questions = adapter.load_questions_without_vectors()
        ids = {q.id for q in questions}
        assert ids == {"pm1", "pm2"}

    def test_empty_when_all_embedded(self, adapter):
        adapter._questions.insert_many([
            _q("pm1", "BTC?", "polymarket", vector=[0.1]),
        ])
        assert adapter.load_questions_without_vectors() == []

    def test_empty_collection(self, adapter):
        assert adapter.load_questions_without_vectors() == []


# ---------------------------------------------------------------------------
# load_questions_with_vectors
# ---------------------------------------------------------------------------

class TestLoadQuestionsWithVectors:
    def test_returns_only_embedded(self, adapter):
        adapter._questions.insert_many([
            _q("pm1", "BTC?", "polymarket"),
            _q("kl1", "BTC?", "kalshi", vector=[0.1, 0.2]),
        ])
        questions = adapter.load_questions_with_vectors()
        assert len(questions) == 1
        assert questions[0].id == "kl1"
        assert questions[0].vector == [0.1, 0.2]


# ---------------------------------------------------------------------------
# save_vectors
# ---------------------------------------------------------------------------

class TestSaveVectors:
    def test_writes_vector_to_document(self, adapter):
        adapter._questions.insert_one(_q("pm1", "BTC?", "polymarket"))
        q = _mq("pm1", "BTC?", "polymarket")
        q.vector = [0.1, 0.2, 0.3]
        adapter.save_vectors([q])
        doc = adapter._questions.find_one({"id": "pm1"})
        assert doc["vector"] == [0.1, 0.2, 0.3]
        assert "embedded_at" in doc

    def test_skips_questions_without_vector(self, adapter):
        adapter._questions.insert_one(_q("pm1", "BTC?", "polymarket"))
        q = _mq("pm1", "BTC?", "polymarket")  # vector=None
        count = adapter.save_vectors([q])
        assert count == 0

    def test_bulk_write(self, adapter):
        adapter._questions.insert_many([
            _q("pm1", "BTC?", "polymarket"),
            _q("pm2", "ETH?", "polymarket"),
        ])
        q1 = _mq("pm1", "BTC?", "polymarket")
        q1.vector = [1.0, 0.0]
        q2 = _mq("pm2", "ETH?", "polymarket")
        q2.vector = [0.0, 1.0]
        adapter.save_vectors([q1, q2])
        assert adapter._questions.find_one({"id": "pm1"})["vector"] == [1.0, 0.0]
        assert adapter._questions.find_one({"id": "pm2"})["vector"] == [0.0, 1.0]


# ---------------------------------------------------------------------------
# save_candidates and load_candidates
# ---------------------------------------------------------------------------

def _make_pair(id_a: str, id_b: str, score: float, negation: bool = False) -> CandidatePair:
    import hashlib
    qa = _mq(id_a, f"Question {id_a}", "polymarket", price=0.60)
    qb = _mq(id_b, f"Question {id_b}", "kalshi", price=0.40)
    pair_id = hashlib.sha256(f"{id_a}|{id_b}".encode()).hexdigest()[:16]
    return CandidatePair(
        id=pair_id,
        question_a=qa,
        question_b=qb,
        similarity_score=score,
        has_potential_negation=negation,
        negation_tokens=["not"] if negation else [],
    )


class TestSaveCandidates:
    def test_saves_all_fields(self, adapter):
        pair = _make_pair("pm1", "kl1", 0.92)
        adapter.save_candidates([pair])
        doc = adapter._candidates.find_one({"id": pair.id})
        assert doc is not None
        assert doc["similarity_score"] == pytest.approx(0.92, abs=0.001)
        assert doc["market_a"] == "polymarket"
        assert doc["market_b"] == "kalshi"
        assert doc["price_spread"] == pytest.approx(0.20, abs=0.001)
        assert doc["has_potential_negation"] is False

    def test_upsert_no_duplicates_on_rerun(self, adapter):
        pair = _make_pair("pm1", "kl1", 0.92)
        adapter.save_candidates([pair])
        adapter.save_candidates([pair])  # second run
        assert adapter._candidates.count_documents({}) == 1

    def test_negation_flag_stored(self, adapter):
        pair = _make_pair("pm1", "kl1", 0.95, negation=True)
        adapter.save_candidates([pair])
        doc = adapter._candidates.find_one({"id": pair.id})
        assert doc["has_potential_negation"] is True
        assert "not" in doc["negation_tokens"]

    def test_empty_list_is_noop(self, adapter):
        count = adapter.save_candidates([])
        assert count == 0


class TestLoadCandidates:
    def test_filters_by_min_score(self, adapter):
        adapter.save_candidates([
            _make_pair("pm1", "kl1", 0.95),
            _make_pair("pm2", "kl2", 0.80),
            _make_pair("pm3", "kl3", 0.65),
        ])
        results = adapter.load_candidates(min_score=0.85)
        assert len(results) == 1
        assert results[0]["similarity_score"] == pytest.approx(0.95, abs=0.001)

    def test_sorted_by_score_descending(self, adapter):
        adapter.save_candidates([
            _make_pair("pm1", "kl1", 0.75),
            _make_pair("pm2", "kl2", 0.95),
            _make_pair("pm3", "kl3", 0.85),
        ])
        results = adapter.load_candidates(min_score=0.0)
        scores = [r["similarity_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_no_mongo_id_in_results(self, adapter):
        adapter.save_candidates([_make_pair("pm1", "kl1", 0.90)])
        results = adapter.load_candidates(min_score=0.0)
        assert "_id" not in results[0]


# ---------------------------------------------------------------------------
# count_questions
# ---------------------------------------------------------------------------

class TestCountQuestions:
    def test_counts_per_market(self, adapter):
        adapter._questions.insert_many([
            _q("pm1", "A", "polymarket"),
            _q("pm2", "B", "polymarket"),
            _q("kl1", "C", "kalshi"),
        ])
        counts = adapter.count_questions()
        assert counts["polymarket"] == 2
        assert counts["kalshi"] == 1
