"""Tests for CandidateFinder and related models."""

import pytest

from vector_db.candidate_finder import CandidateFinder, _detect_negation
from vector_db.embedder import HashEmbedder
from vector_db.models import CandidatePair, MarketQuestion


def _q(id: str, text: str, market: str, price: float = 0.5) -> MarketQuestion:
    return MarketQuestion(id=id, text=text, market=market, price=price)


@pytest.fixture
def finder():
    """CandidateFinder with deterministic hash embedder — no model download."""
    return CandidateFinder(embedder=HashEmbedder(dimensions=64), similarity_threshold=0.0)


# ---------------------------------------------------------------------------
# MarketQuestion model validation
# ---------------------------------------------------------------------------
class TestMarketQuestion:
    def test_valid_question(self):
        q = _q("1", "Will Bitcoin hit $100k?", "polymarket")
        assert q.id == "1"
        assert q.market == "polymarket"

    def test_empty_id_raises(self):
        with pytest.raises(ValueError, match="id"):
            MarketQuestion(id="", text="Some text", market="polymarket")

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="text"):
            MarketQuestion(id="1", text="  ", market="polymarket")

    def test_empty_market_raises(self):
        with pytest.raises(ValueError, match="market"):
            MarketQuestion(id="1", text="Some text", market="")

    def test_invalid_price_raises(self):
        with pytest.raises(ValueError, match="price"):
            MarketQuestion(id="1", text="Some text", market="polymarket", price=1.5)

    def test_price_boundary_valid(self):
        q = MarketQuestion(id="1", text="Some text", market="polymarket", price=0.0)
        assert q.price == 0.0
        q2 = MarketQuestion(id="2", text="Some text", market="polymarket", price=1.0)
        assert q2.price == 1.0


# ---------------------------------------------------------------------------
# Negation detection
# ---------------------------------------------------------------------------
class TestDetectNegation:
    def test_no_negation(self):
        has_neg, tokens = _detect_negation("Will X happen?", "Will X occur?")
        assert not has_neg
        assert tokens == []

    def test_asymmetric_negation(self):
        has_neg, tokens = _detect_negation("Will X happen?", "Will X not happen?")
        assert has_neg
        assert "not" in tokens

    def test_symmetric_negation_not_flagged(self):
        # Both texts contain "not" — symmetric, not flagged
        has_neg, tokens = _detect_negation("Will X not happen?", "Will X not occur?")
        assert not has_neg

    def test_multiple_negation_tokens(self):
        has_neg, tokens = _detect_negation(
            "Will X happen?",
            "Will X never fail to occur?",
        )
        assert has_neg
        assert "never" in tokens or "fail" in tokens

    def test_case_insensitive(self):
        has_neg, tokens = _detect_negation("Will X Happen?", "Will X NOT happen?")
        assert has_neg


# ---------------------------------------------------------------------------
# CandidateFinder.find_candidates
# ---------------------------------------------------------------------------
class TestCandidateFinder:
    def test_returns_empty_for_empty_inputs(self, finder):
        assert finder.find_candidates([], []) == []
        assert finder.find_candidates([_q("a", "text", "pm")], []) == []
        assert finder.find_candidates([], [_q("b", "text", "kl")]) == []

    def test_finds_identical_pair(self, finder):
        qa = [_q("pm1", "Will Bitcoin reach $100k?", "polymarket")]
        qb = [_q("kl1", "Will Bitcoin reach $100k?", "kalshi")]
        pairs = finder.find_candidates(qa, qb)
        assert len(pairs) == 1
        assert pairs[0].similarity_score == pytest.approx(1.0, abs=1e-4)

    def test_sorted_by_score_descending(self, finder):
        qa = [_q("pm1", "Bitcoin price target", "polymarket")]
        qb = [
            _q("kl1", "Bitcoin price target", "kalshi"),
            _q("kl2", "football game result", "kalshi"),
        ]
        pairs = finder.find_candidates(qa, qb)
        scores = [p.similarity_score for p in pairs]
        assert scores == sorted(scores, reverse=True)

    def test_negation_flagged(self, finder):
        qa = [_q("pm1", "Will Trump win?", "polymarket")]
        qb = [_q("kl1", "Will Trump not win?", "kalshi")]
        pairs = finder.find_candidates(qa, qb)
        assert len(pairs) == 1
        assert pairs[0].has_potential_negation
        assert "not" in pairs[0].negation_tokens

    def test_no_self_market_dedup(self, finder):
        """Cross-market only: a,a = same IDs across markets are allowed."""
        qa = [_q("1", "Bitcoin hits 100k", "polymarket")]
        qb = [_q("1", "Bitcoin hits 100k", "kalshi")]
        # Same text, different market → valid pair
        pairs = finder.find_candidates(qa, qb)
        assert len(pairs) == 1

    def test_threshold_filters_low_similarity(self):
        strict_finder = CandidateFinder(
            embedder=HashEmbedder(dimensions=64),
            similarity_threshold=0.99,
        )
        qa = [_q("pm1", "Bitcoin price prediction", "polymarket")]
        qb = [_q("kl1", "Ethereum staking yield", "kalshi")]
        pairs = strict_finder.find_candidates(qa, qb)
        assert all(p.similarity_score >= 0.99 for p in pairs)

    def test_pair_ids_are_deterministic(self, finder):
        qa = [_q("pm1", "Will X happen?", "polymarket")]
        qb = [_q("kl1", "Will X happen?", "kalshi")]
        pairs1 = finder.find_candidates(qa, qb)
        pairs2 = finder.find_candidates(qa, qb)
        assert pairs1[0].id == pairs2[0].id

    def test_find_candidates_all_markets(self, finder):
        questions = {
            "polymarket": [_q("pm1", "Bitcoin 100k by end of year", "polymarket")],
            "kalshi": [_q("kl1", "Bitcoin reaches 100000 by December", "kalshi")],
            "manifold": [_q("mf1", "Soccer world cup winner 2026", "manifold")],
        }
        pairs = finder.find_candidates_all_markets(questions)
        # Should find pairs between polymarket-kalshi (similar texts)
        assert isinstance(pairs, list)
        # All pairs should be cross-market
        for p in pairs:
            assert p.question_a.market != p.question_b.market

    @pytest.mark.slow
    def test_find_candidates_with_transformer(self):
        """Integration: real model should score semantically similar questions high."""
        from vector_db.embedder import TransformerEmbedder
        finder = CandidateFinder(
            embedder=TransformerEmbedder(),
            similarity_threshold=0.7,
        )
        qa = [
            _q("pm1", "Will the Federal Reserve raise interest rates in 2025?", "polymarket"),
            _q("pm2", "Will Bitcoin exceed $150,000 by end of 2025?", "polymarket"),
        ]
        qb = [
            _q("kl1", "Federal Reserve rate hike before 2026?", "kalshi"),
            _q("kl2", "BTC price above 150k USD by December 2025?", "kalshi"),
            _q("kl3", "Who wins the 2026 FIFA World Cup?", "kalshi"),
        ]
        pairs = finder.find_candidates(qa, qb)
        # Fed question should pair with Fed question
        fed_pairs = [p for p in pairs if "Federal" in p.question_a.text or "Federal" in p.question_b.text]
        assert len(fed_pairs) >= 1
        assert fed_pairs[0].similarity_score >= 0.7
