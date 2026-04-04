"""Tests for Phase 3 Engine — end-to-end orchestration."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from algorithm.models import CandidatePair, Market
from algorithm.Phase_3.engine import Phase3Engine
from algorithm.Phase_3.models import LLMJudgment, RelationshipType, Verdict


def _market(market_id: str, question: str, close_time: datetime | None = None) -> Market:
    return Market(
        platform="test",
        market_id=market_id,
        question=question,
        outcomes=["Yes", "No"],
        prices={"Yes": 0.5, "No": 0.5},
        close_time=close_time,
        fetched_at=datetime.utcnow(),
    )


def _pair(candidate_id: str, market_a: Market, market_b: Market) -> CandidatePair:
    return CandidatePair(
        candidate_id=candidate_id,
        market_a=market_a,
        market_b=market_b,
        embedding_similarity=0.9,
    )


_ACCEPT_JUDGMENT = LLMJudgment(
    verdict=Verdict.ACCEPT,
    relationship_type=RelationshipType.EQUIVALENT,
    confidence=0.92,
    reasoning="Same event on two platforms.",
    outcome_hints={"Yes": "Yes", "No": "No"},
)

_REJECT_JUDGMENT = LLMJudgment(
    verdict=Verdict.REJECT,
    relationship_type=RelationshipType.UNRELATED,
    confidence=0.95,
    reasoning="Different events.",
    outcome_hints={},
)


def _mock_judge_response(judgment: LLMJudgment) -> MagicMock:
    content = judgment.model_dump_json()
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


class TestPhase3Engine:
    @pytest.mark.asyncio
    async def test_accept_equivalent_markets(self) -> None:
        engine = Phase3Engine()
        a = _market("a", "Will Bitcoin reach $100k by end of 2025?", datetime(2025, 12, 31))
        b = _market("b", "Will BTC hit $100,000 before 2026?", datetime(2025, 12, 31))
        pair = _pair("test_001", a, b)

        with patch.object(
            engine._llm_judge._client.chat.completions,
            "create",
            new=AsyncMock(return_value=_mock_judge_response(_ACCEPT_JUDGMENT)),
        ):
            decision = await engine.process_candidate(pair)

        assert decision.candidate_id == "test_001"
        assert decision.verdict == Verdict.ACCEPT
        assert decision.confidence > 0.0
        assert decision.processing_time_ms > 0.0

    @pytest.mark.asyncio
    async def test_reject_on_hard_contradiction(self) -> None:
        """Nomination vs general election should hard-reject without calling LLM."""
        engine = Phase3Engine()
        a = _market("a", "Will Biden win the Democratic primary nomination?")
        b = _market("b", "Will Biden win the general election?")
        pair = _pair("test_002", a, b)

        with patch.object(
            engine._llm_judge._client.chat.completions,
            "create",
            new=AsyncMock(side_effect=Exception("should not be called")),
        ):
            decision = await engine.process_candidate(pair)

        assert decision.verdict == Verdict.REJECT
        assert len(decision.contradiction_flags) > 0

    @pytest.mark.asyncio
    async def test_dead_letter_on_exception(self) -> None:
        """Unhandled exception should produce REVIEW verdict, not crash."""
        engine = Phase3Engine()
        a = _market("a", "Will X happen?")
        b = _market("b", "Will X happen?")
        pair = _pair("test_003", a, b)

        with patch.object(
            engine._llm_judge._client.chat.completions,
            "create",
            new=AsyncMock(side_effect=Exception("API down")),
        ):
            decision = await engine.process_candidate(pair)

        assert decision.verdict == Verdict.REVIEW

    @pytest.mark.asyncio
    async def test_batch_processing(self) -> None:
        """process_batch should return one decision per candidate."""
        engine = Phase3Engine()
        pairs = [
            _pair(
                f"batch_{i:03d}",
                _market(f"a_{i}", f"Will thing {i} happen by 2025-12-31?"),
                _market(f"b_{i}", f"Will thing {i} occur by end of 2025?"),
            )
            for i in range(3)
        ]

        with patch.object(
            engine._llm_judge._client.chat.completions,
            "create",
            new=AsyncMock(return_value=_mock_judge_response(_ACCEPT_JUDGMENT)),
        ):
            decisions = await engine.process_batch(pairs)

        assert len(decisions) == 3
        assert all(d.candidate_id.startswith("batch_") for d in decisions)

    @pytest.mark.asyncio
    async def test_decision_has_all_fields(self) -> None:
        engine = Phase3Engine()
        a = _market("a", "Will X happen by 2025-12-31?")
        b = _market("b", "Will X happen by 2025-12-31?")
        pair = _pair("test_004", a, b)

        with patch.object(
            engine._llm_judge._client.chat.completions,
            "create",
            new=AsyncMock(return_value=_mock_judge_response(_ACCEPT_JUDGMENT)),
        ):
            decision = await engine.process_candidate(pair)

        assert decision.template_labels is not None
        assert decision.extracted_features_a is not None
        assert decision.extracted_features_b is not None
        assert decision.llm_verdict is not None
        assert decision.outcome_mapping is not None
        assert decision.arb_compatibility is not None
