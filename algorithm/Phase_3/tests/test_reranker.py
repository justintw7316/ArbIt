"""Tests for Layer 4 — Reranker."""

from datetime import datetime

import pytest

from algorithm.models import Market
from algorithm.Phase_3.reranker import MockReranker, OpenAIReranker, build_reranker


def _market(
    market_id: str,
    question: str,
    outcomes: list[str] | None = None,
    close_time: datetime | None = None,
) -> Market:
    return Market(
        platform="test",
        market_id=market_id,
        question=question,
        outcomes=outcomes or ["Yes", "No"],
        prices={"Yes": 0.5, "No": 0.5},
        close_time=close_time,
        fetched_at=datetime.utcnow(),
    )


class TestMockReranker:
    def test_score_range(self) -> None:
        r = MockReranker()
        a = _market("a", "Will Bitcoin reach $100k by end of 2025?")
        b = _market("b", "Will BTC hit 100000 before 2026?")
        result = r.score(a, b)
        assert 0.0 <= result.score <= 1.0

    def test_identical_markets_high_score(self) -> None:
        r = MockReranker()
        m = _market("a", "Will Bitcoin reach $100k by 2025-12-31?")
        result = r.score(m, m)
        assert result.score > 0.7

    def test_unrelated_markets_low_score(self) -> None:
        r = MockReranker()
        a = _market("a", "Will it rain tomorrow in Tokyo?")
        b = _market("b", "Will the Federal Reserve raise interest rates?")
        result = r.score(a, b)
        assert result.score < 0.8

    def test_components_present(self) -> None:
        r = MockReranker()
        a = _market("a", "Will X happen?")
        b = _market("b", "Will Y happen?")
        result = r.score(a, b)
        assert "text_overlap" in result.components
        assert "date_proximity" in result.components
        assert "outcome_overlap" in result.components

    def test_reranker_type_label(self) -> None:
        r = MockReranker()
        a = _market("a", "Q?")
        b = _market("b", "Q?")
        result = r.score(a, b)
        assert result.reranker_type == "mock"

    def test_complement_outcomes(self) -> None:
        """YES/NO outcomes on each side should score reasonably."""
        r = MockReranker()
        a = _market("a", "Will X win?", outcomes=["Yes", "No"])
        b = _market("b", "Will X lose?", outcomes=["Yes", "No"])
        result = r.score(a, b)
        assert result.score >= 0.0

    def test_date_proximity_same_date(self) -> None:
        r = MockReranker()
        dt = datetime(2025, 12, 31)
        a = _market("a", "Will X happen?", close_time=dt)
        b = _market("b", "Will X happen?", close_time=dt)
        result = r.score(a, b)
        assert result.components["date_proximity"] == 1.0


class TestBuildReranker:
    def test_build_mock(self) -> None:
        r = build_reranker("mock")
        assert isinstance(r, MockReranker)

    def test_build_openai(self) -> None:
        r = build_reranker("openai", api_key="")
        assert isinstance(r, OpenAIReranker)

    def test_openai_fallback_without_key(self) -> None:
        r = build_reranker("openai", api_key="")
        a = _market("a", "Q?")
        b = _market("b", "Q?")
        result = r.score(a, b)
        assert result.reranker_type == "openai_stub_fallback"
