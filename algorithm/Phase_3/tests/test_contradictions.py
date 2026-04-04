"""Tests for Layer 3 — Hard Contradiction Filter."""

from datetime import datetime

import pytest

from algorithm.models import Market
from algorithm.Phase_3.classifier import classify_market
from algorithm.Phase_3.contradictions import check_contradictions
from algorithm.Phase_3.extractor import extract_features
from algorithm.Phase_3.models import MarketTemplate, TemplateResult


def _market(market_id: str, question: str, description: str | None = None) -> Market:
    return Market(
        platform="test",
        market_id=market_id,
        question=question,
        description=description,
        outcomes=["Yes", "No"],
        prices={"Yes": 0.5, "No": 0.5},
        fetched_at=datetime.utcnow(),
    )


def _check(market_a: Market, market_b: Market):  # type: ignore[no-untyped-def]
    fa = extract_features(market_a)
    fb = extract_features(market_b)
    ta = classify_market(market_a)
    tb = classify_market(market_b)
    return check_contradictions(fa, fb, ta, tb)


class TestCheckContradictions:
    def test_identical_questions_no_contradiction(self) -> None:
        m = _market("x", "Will Bitcoin reach $100,000 by 2025-12-31?")
        result = _check(m, m)
        assert not result.hard_reject

    def test_no_contradiction_on_missing_entities(self) -> None:
        """Missing primary entity is neutral — should never reject."""
        a = _market("a", "Will it happen?")
        b = _market("b", "Will it occur?")
        result = _check(a, b)
        assert not result.hard_reject

    def test_date_gap_within_tolerance(self) -> None:
        a = _market("a", "Will X happen by 2025-12-31?")
        b = _market("b", "Will X happen by 2026-01-15?")  # 15 days — within 30-day default
        result = _check(a, b)
        assert not result.hard_reject

    def test_date_gap_exceeds_tolerance(self) -> None:
        a = _market("a", "Will X happen by 2025-01-01?")
        b = _market("b", "Will X happen by 2025-06-01?")  # 150 days
        result = _check(a, b)
        assert result.hard_reject
        assert any("date_gap" in f for f in result.flags)

    def test_nomination_vs_general_election(self) -> None:
        a = _market("a", "Will Biden win the Democratic primary nomination?")
        b = _market("b", "Will Biden win the general election?")
        result = _check(a, b)
        assert result.hard_reject
        assert any("nomination" in f for f in result.flags)

    def test_threshold_mismatch_large(self) -> None:
        a = _market("a", "Will Bitcoin reach $100,000?")
        b = _market("b", "Will Bitcoin reach $200,000?")
        result = _check(a, b)
        # Thresholds differ by 100% — soft flag only, LLM decides
        assert any("threshold_mismatch" in f for f in result.flags)
        # threshold_mismatch alone must NOT hard-reject (unit differences cause false positives)
        assert not result.hard_reject

    def test_threshold_mismatch_within_5pct(self) -> None:
        """Small threshold variation (≤ 5%) should not reject."""
        a = _market("a", "Will price exceed $100,000?")
        b = _market("b", "Will price exceed $101,000?")
        result = _check(a, b)
        # 1% difference — should not hard reject on thresholds
        if result.hard_reject:
            # Only acceptable if another flag triggered it
            assert not any("threshold_mismatch" in f for f in result.flags)

    def test_contradiction_result_structure(self) -> None:
        a = _market("a", "Will X happen?")
        b = _market("b", "Will X happen?")
        result = _check(a, b)
        assert isinstance(result.hard_reject, bool)
        assert isinstance(result.flags, list)
        assert 0.0 <= result.confidence <= 1.0
