"""Tests for Layer 1 — Template Classifier."""

from datetime import datetime

import pytest

from algorithm.models import Market
from algorithm.Phase_3.classifier import classify_market, classify_pair
from algorithm.Phase_3.models import MarketTemplate


def _market(market_id: str, question: str, outcomes: list[str] | None = None) -> Market:
    return Market(
        platform="test",
        market_id=market_id,
        question=question,
        outcomes=outcomes or ["Yes", "No"],
        prices={"Yes": 0.5, "No": 0.5},
        fetched_at=datetime.utcnow(),
    )


class TestClassifyMarket:
    def test_election_event(self) -> None:
        m = _market("e1", "Will Donald Trump win the 2024 presidential election?")
        result = classify_market(m)
        assert result.primary_template == MarketTemplate.ELECTION_EVENT
        assert result.confidence > 0.7

    def test_threshold_event(self) -> None:
        m = _market("t1", "Will Bitcoin reach $100,000 by end of 2025?")
        result = classify_market(m)
        assert result.primary_template in (
            MarketTemplate.THRESHOLD_EVENT,
            MarketTemplate.BY_DATE_EVENT,
        )

    def test_sports_result(self) -> None:
        m = _market("s1", "Will the Kansas City Chiefs win the Super Bowl?")
        result = classify_market(m)
        assert result.primary_template == MarketTemplate.SPORTS_RESULT

    def test_approval_event(self) -> None:
        m = _market("a1", "Will Congress approve the new spending bill?")
        result = classify_market(m)
        assert result.primary_template == MarketTemplate.APPROVAL_EVENT

    def test_unknown_template(self) -> None:
        m = _market("u1", "xyz???")
        result = classify_market(m)
        assert result.primary_template == MarketTemplate.UNKNOWN
        assert result.confidence == 0.5

    def test_multi_outcome_by_count(self) -> None:
        outcomes = ["A", "B", "C", "D"]
        m = _market("m1", "Who will win?", outcomes=outcomes)
        result = classify_market(m)
        assert result.primary_template in (
            MarketTemplate.MULTI_OUTCOME_EXHAUSTIVE,
            MarketTemplate.BINARY_WINNER,
        )

    def test_result_has_market_id(self) -> None:
        m = _market("id123", "Will X happen?")
        result = classify_market(m)
        assert result.market_id == "id123"

    def test_secondary_template_optional(self) -> None:
        m = _market("e2", "Will Joe Biden win the election by a large margin?")
        result = classify_market(m)
        assert result.secondary_template is None or isinstance(
            result.secondary_template, MarketTemplate
        )


class TestClassifyPair:
    def test_returns_two_results(self) -> None:
        a = _market("a", "Will A happen?")
        b = _market("b", "Will B happen?")
        r_a, r_b = classify_pair(a, b)
        assert r_a.market_id == "a"
        assert r_b.market_id == "b"
