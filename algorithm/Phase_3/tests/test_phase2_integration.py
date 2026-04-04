"""Tests for Phase 2 -> Phase 3 integration."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from algorithm.Phase_2.embedder import HashEmbedder
from algorithm.Phase_2.models import CandidatePair as Phase2CandidatePair
from algorithm.Phase_2.models import MarketQuestion
from algorithm.Phase_2.pipeline import ArbitragePipeline
from algorithm.Phase_3.adapters import (
    ensure_canonical_candidate,
    phase2_candidate_to_canonical,
    phase2_question_to_market,
)
from algorithm.Phase_3.engine import Phase3Engine
from algorithm.Phase_3.models import LLMJudgment, RelationshipType, Verdict


_ACCEPT_JUDGMENT = LLMJudgment(
    verdict=Verdict.ACCEPT,
    relationship_type=RelationshipType.EQUIVALENT,
    confidence=0.9,
    reasoning="Equivalent market questions.",
    outcome_hints={"Yes": "Yes", "No": "No"},
)


def _mock_judge_response(judgment: LLMJudgment) -> MagicMock:
    choice = MagicMock()
    choice.message.content = judgment.model_dump_json()
    response = MagicMock()
    response.choices = [choice]
    return response


def _question(
    question_id: str,
    market: str,
    text: str,
    price: float,
) -> MarketQuestion:
    return MarketQuestion(
        id=question_id,
        market=market,
        text=text,
        price=price,
        metadata={
            "outcomes": ["Yes", "No"],
            "close_time": "2025-12-31T00:00:00Z",
            "fees": 0.02,
        },
    )


class TestPhase2Adapters:
    def test_question_to_market_uses_phase2_metadata(self) -> None:
        question = MarketQuestion(
            id="pm_btc",
            market="polymarket",
            text="Will Bitcoin reach $100,000 by end of 2025?",
            price=0.42,
            metadata={
                "market_id": "poly_btc_100k",
                "description": "BTC price threshold market",
                "outcomes": ["Yes", "No"],
                "prices": {"Yes": 0.42, "No": 0.58},
                "fees": 0.01,
                "close_time": "2025-12-31T00:00:00Z",
                "resolution_rules": "Polymarket official rules",
            },
        )

        market = phase2_question_to_market(question)

        assert market.platform == "polymarket"
        assert market.market_id == "poly_btc_100k"
        assert market.question == question.text
        assert market.prices == {"Yes": 0.42, "No": 0.58}
        assert market.outcomes == ["Yes", "No"]
        assert market.close_time == datetime.fromisoformat("2025-12-31T00:00:00+00:00")

    def test_question_to_market_falls_back_to_binary_prices(self) -> None:
        question = MarketQuestion(
            id="kl_btc",
            market="kalshi",
            text="Will Bitcoin exceed $100,000 before 2026?",
            price=0.47,
        )

        market = phase2_question_to_market(question)

        assert market.market_id == "kl_btc"
        assert market.outcomes == ["Yes", "No"]
        assert market.prices == {"Yes": 0.47, "No": 0.53}

    def test_candidate_adapter_preserves_phase2_signals(self) -> None:
        candidate = Phase2CandidatePair(
            id="pair_123",
            question_a=_question("pm_1", "polymarket", "Will X happen?", 0.4),
            question_b=_question("kl_1", "kalshi", "Will X happen?", 0.45),
            similarity_score=0.88,
            has_potential_negation=True,
            negation_tokens=["not"],
        )

        canonical = phase2_candidate_to_canonical(candidate)

        assert canonical.candidate_id == "pair_123"
        assert canonical.embedding_similarity == 0.88
        assert canonical.metadata["has_potential_negation"] is True
        assert canonical.metadata["negation_tokens"] == ["not"]


class TestPhase2ToPhase3Workflow:
    @pytest.mark.asyncio
    async def test_phase2_pipeline_output_flows_into_phase3(self) -> None:
        pipeline = ArbitragePipeline(
            embedder=HashEmbedder(dimensions=64),
            similarity_threshold=0.99,
        )
        questions = [
            _question(
                "pm_btc",
                "polymarket",
                "Will Bitcoin reach $100,000 by end of 2025?",
                0.42,
            ),
            _question(
                "kl_btc",
                "kalshi",
                "Will Bitcoin reach $100,000 by end of 2025?",
                0.47,
            ),
        ]
        phase2_candidates = pipeline.run(questions)

        assert len(phase2_candidates) == 1

        engine = Phase3Engine()
        with patch.object(
            engine._llm_judge._client.chat.completions,
            "create",
            new=AsyncMock(return_value=_mock_judge_response(_ACCEPT_JUDGMENT)),
        ):
            decision = await engine.process_candidate(phase2_candidates[0])

        assert decision.verdict == Verdict.ACCEPT
        assert decision.candidate_id == phase2_candidates[0].id
        assert decision.outcome_mapping is not None
        assert decision.arb_compatibility is not None

    @pytest.mark.asyncio
    async def test_process_batch_accepts_phase2_candidate_pairs(self) -> None:
        candidates = [
            Phase2CandidatePair(
                id=f"pair_{i}",
                question_a=_question(
                    f"pm_{i}",
                    "polymarket",
                    f"Will thing {i} happen by end of 2025?",
                    0.4,
                ),
                question_b=_question(
                    f"kl_{i}",
                    "kalshi",
                    f"Will thing {i} happen by end of 2025?",
                    0.45,
                ),
                similarity_score=1.0,
            )
            for i in range(2)
        ]
        engine = Phase3Engine()

        with patch.object(
            engine._llm_judge._client.chat.completions,
            "create",
            new=AsyncMock(return_value=_mock_judge_response(_ACCEPT_JUDGMENT)),
        ):
            decisions = await engine.process_batch(candidates)

        assert len(decisions) == 2
        assert [d.candidate_id for d in decisions] == ["pair_0", "pair_1"]

    def test_ensure_canonical_candidate_returns_canonical_type(self) -> None:
        candidate = Phase2CandidatePair(
            id="pair_a",
            question_a=_question("pm_a", "polymarket", "Will A happen?", 0.4),
            question_b=_question("kl_a", "kalshi", "Will A happen?", 0.45),
            similarity_score=0.91,
        )

        canonical = ensure_canonical_candidate(candidate)

        assert canonical.candidate_id == "pair_a"
        assert canonical.market_a.platform == "polymarket"
        assert canonical.market_b.platform == "kalshi"
