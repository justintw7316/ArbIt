"""Tests for Layer 5 — LLM Judge (using mocked API calls)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from algorithm.models import Market
from algorithm.Phase_3.llm_judge import LLMJudge
from algorithm.Phase_3.models import LLMJudgment, RelationshipType, Verdict


def _market(market_id: str, question: str) -> Market:
    return Market(
        platform="test",
        market_id=market_id,
        question=question,
        outcomes=["Yes", "No"],
        prices={"Yes": 0.5, "No": 0.5},
        fetched_at=datetime.utcnow(),
    )


_VALID_RESPONSE = """{
  "verdict": "ACCEPT",
  "relationship_type": "equivalent",
  "confidence": 0.9,
  "reasoning": "Both markets refer to the same event.",
  "outcome_hints": {"Yes": "Yes", "No": "No"}
}"""

_REJECT_RESPONSE = """{
  "verdict": "REJECT",
  "relationship_type": "unrelated",
  "confidence": 0.95,
  "reasoning": "Markets refer to different events.",
  "outcome_hints": {}
}"""

_MALFORMED_RESPONSE = "not valid json at all {{"


def _make_mock_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


class TestLLMJudgeParsing:
    def test_parse_valid_accept(self) -> None:
        judge = LLMJudge()
        result = judge._parse_response(_VALID_RESPONSE)
        assert result.verdict == Verdict.ACCEPT
        assert result.relationship_type == RelationshipType.EQUIVALENT
        assert result.confidence == 0.9
        assert result.outcome_hints == {"Yes": "Yes", "No": "No"}

    def test_parse_reject(self) -> None:
        judge = LLMJudge()
        result = judge._parse_response(_REJECT_RESPONSE)
        assert result.verdict == Verdict.REJECT
        assert result.relationship_type == RelationshipType.UNRELATED

    def test_parse_markdown_fenced(self) -> None:
        fenced = f"```json\n{_VALID_RESPONSE}\n```"
        judge = LLMJudge()
        result = judge._parse_response(fenced)
        assert result.verdict == Verdict.ACCEPT

    def test_confidence_clipped_to_range(self) -> None:
        response = '{"verdict": "ACCEPT", "relationship_type": "equivalent", "confidence": 1.5, "reasoning": "x", "outcome_hints": {}}'
        judge = LLMJudge()
        result = judge._parse_response(response)
        assert result.confidence <= 1.0

    def test_unknown_verdict_becomes_review(self) -> None:
        response = '{"verdict": "MAYBE", "relationship_type": "equivalent", "confidence": 0.5, "reasoning": "x", "outcome_hints": {}}'
        judge = LLMJudge()
        result = judge._parse_response(response)
        assert result.verdict == Verdict.REVIEW

    def test_unknown_relationship_becomes_unrelated(self) -> None:
        response = '{"verdict": "ACCEPT", "relationship_type": "weird_type", "confidence": 0.5, "reasoning": "x", "outcome_hints": {}}'
        judge = LLMJudge()
        result = judge._parse_response(response)
        assert result.relationship_type == RelationshipType.UNRELATED


class TestLLMJudgeAsync:
    @pytest.mark.asyncio
    async def test_successful_judge_call(self) -> None:
        judge = LLMJudge()
        mock_response = _make_mock_response(_VALID_RESPONSE)

        with patch.object(
            judge._client.chat.completions, "create", new=AsyncMock(return_value=mock_response)
        ):
            a = _market("a", "Will Bitcoin reach $100k?")
            b = _market("b", "Will BTC hit $100,000?")
            result = await judge.judge(a, b)

        assert result.verdict == Verdict.ACCEPT
        assert isinstance(result, LLMJudgment)

    @pytest.mark.asyncio
    async def test_dead_letter_on_persistent_failure(self) -> None:
        """After max_retries failures, returns REVIEW verdict."""
        judge = LLMJudge()

        with patch.object(
            judge._client.chat.completions,
            "create",
            new=AsyncMock(side_effect=Exception("API error")),
        ):
            a = _market("a", "Q?")
            b = _market("b", "Q?")
            result = await judge.judge(a, b)

        assert result.verdict == Verdict.REVIEW
        assert "API error" in result.reasoning or "failed" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_retry_on_malformed_then_succeed(self) -> None:
        """Returns correct result after initial malformed response."""
        judge = LLMJudge()
        bad_resp = _make_mock_response(_MALFORMED_RESPONSE)
        good_resp = _make_mock_response(_VALID_RESPONSE)

        with patch.object(
            judge._client.chat.completions,
            "create",
            new=AsyncMock(side_effect=[
                Exception("parse error"),
                good_resp,
            ]),
        ):
            a = _market("a", "Q?")
            b = _market("b", "Q?")
            result = await judge.judge(a, b)

        assert result.verdict == Verdict.ACCEPT
