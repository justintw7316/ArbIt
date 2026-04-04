"""Tests for Layer 6a — Outcome Mapping."""

from datetime import datetime

import pytest

from algorithm.models import Market
from algorithm.Phase_3.mapping import determine_outcome_mapping
from algorithm.Phase_3.models import (
    LLMJudgment,
    OutcomeMappingType,
    RelationshipType,
    Verdict,
)


def _market(market_id: str, outcomes: list[str] | None = None) -> Market:
    return Market(
        platform="test",
        market_id=market_id,
        question="Will X happen?",
        outcomes=outcomes or ["Yes", "No"],
        prices={o: 0.5 for o in (outcomes or ["Yes", "No"])},
        fetched_at=datetime.utcnow(),
    )


def _judgment(
    rel: RelationshipType,
    confidence: float = 0.9,
    outcome_hints: dict[str, str] | None = None,
) -> LLMJudgment:
    return LLMJudgment(
        verdict=Verdict.ACCEPT,
        relationship_type=rel,
        confidence=confidence,
        reasoning="test",
        outcome_hints=outcome_hints or {},
    )


class TestDetermineOutcomeMapping:
    def test_llm_hints_take_priority(self) -> None:
        a = _market("a")
        b = _market("b")
        j = _judgment(RelationshipType.EQUIVALENT, outcome_hints={"Yes": "Yes", "No": "No"})
        result = determine_outcome_mapping(a, b, j)
        assert result.mapping_type == OutcomeMappingType.DIRECT
        assert result.mappings == {"Yes": "Yes", "No": "No"}

    def test_equivalent_binary_direct_mapping(self) -> None:
        a = _market("a", ["Yes", "No"])
        b = _market("b", ["Yes", "No"])
        j = _judgment(RelationshipType.EQUIVALENT)
        result = determine_outcome_mapping(a, b, j)
        assert result.mapping_type == OutcomeMappingType.DIRECT
        assert len(result.mappings) == 2

    def test_complement_inverted_mapping(self) -> None:
        a = _market("a", ["Yes", "No"])
        b = _market("b", ["Yes", "No"])
        j = _judgment(RelationshipType.COMPLEMENT)
        result = determine_outcome_mapping(a, b, j)
        assert result.mapping_type == OutcomeMappingType.INVERTED

    def test_subset_mapping_type(self) -> None:
        a = _market("a")
        b = _market("b")
        j = _judgment(RelationshipType.SUBSET)
        result = determine_outcome_mapping(a, b, j)
        assert result.mapping_type == OutcomeMappingType.SUBSET_MAPPING

    def test_unrelated_unmappable(self) -> None:
        a = _market("a")
        b = _market("b")
        j = _judgment(RelationshipType.UNRELATED)
        result = determine_outcome_mapping(a, b, j)
        assert result.mapping_type == OutcomeMappingType.UNMAPPABLE

    def test_confidence_propagated(self) -> None:
        a = _market("a", ["Yes", "No"])
        b = _market("b", ["Yes", "No"])
        j = _judgment(RelationshipType.EQUIVALENT, confidence=0.75)
        result = determine_outcome_mapping(a, b, j)
        assert result.confidence > 0.0
