"""Tests for Layer 6b — Arb Compatibility Check."""

from datetime import datetime

import pytest

from algorithm.models import Market
from algorithm.Phase_3.arb_filter import check_arb_compatibility
from algorithm.Phase_3.models import (
    ArbStructureType,
    LLMJudgment,
    OutcomeMappingResult,
    OutcomeMappingType,
    RelationshipType,
    Verdict,
)


def _market(market_id: str, outcomes: list[str] | None = None) -> Market:
    outcomes = outcomes or ["Yes", "No"]
    return Market(
        platform="test",
        market_id=market_id,
        question="Will X happen?",
        outcomes=outcomes,
        prices={o: 0.5 / len(outcomes) for o in outcomes},
        fetched_at=datetime.utcnow(),
    )


def _judgment(rel: RelationshipType, hints: dict[str, str] | None = None) -> LLMJudgment:
    return LLMJudgment(
        verdict=Verdict.ACCEPT,
        relationship_type=rel,
        confidence=0.9,
        reasoning="test",
        outcome_hints=hints or {},
    )


def _mapping(
    mapping_type: OutcomeMappingType,
    mappings: dict[str, str] | None = None,
) -> OutcomeMappingResult:
    return OutcomeMappingResult(
        mapping_type=mapping_type,
        mappings=mappings or {"Yes": "Yes", "No": "No"},
        confidence=0.9,
    )


class TestCheckArbCompatibility:
    def test_unrelated_not_arb(self) -> None:
        a, b = _market("a"), _market("b")
        result = check_arb_compatibility(
            a, b,
            _judgment(RelationshipType.UNRELATED),
            _mapping(OutcomeMappingType.UNMAPPABLE, {}),
        )
        assert not result.is_compatible
        assert result.arb_structure == ArbStructureType.NOT_ARB

    def test_related_not_arb(self) -> None:
        a, b = _market("a"), _market("b")
        result = check_arb_compatibility(
            a, b,
            _judgment(RelationshipType.RELATED_NOT_ARB),
            _mapping(OutcomeMappingType.DIRECT),
        )
        assert not result.is_compatible

    def test_equivalent_binary_pair(self) -> None:
        a = _market("a", ["Yes", "No"])
        b = _market("b", ["Yes", "No"])
        result = check_arb_compatibility(
            a, b,
            _judgment(RelationshipType.EQUIVALENT),
            _mapping(OutcomeMappingType.DIRECT, {"Yes": "Yes", "No": "No"}),
        )
        assert result.is_compatible
        assert result.arb_structure == ArbStructureType.BINARY_PAIR

    def test_legs_populated_for_binary(self) -> None:
        a = _market("a", ["Yes", "No"])
        b = _market("b", ["Yes", "No"])
        result = check_arb_compatibility(
            a, b,
            _judgment(RelationshipType.EQUIVALENT),
            _mapping(OutcomeMappingType.DIRECT, {"Yes": "Yes", "No": "No"}),
        )
        assert len(result.legs) == 2

    def test_unmappable_without_hints_rejected(self) -> None:
        a, b = _market("a"), _market("b")
        j = LLMJudgment(
            verdict=Verdict.ACCEPT,
            relationship_type=RelationshipType.EQUIVALENT,
            confidence=0.9,
            reasoning="test",
            outcome_hints={},
        )
        result = check_arb_compatibility(
            a, b,
            j,
            _mapping(OutcomeMappingType.UNMAPPABLE, {}),
        )
        assert not result.is_compatible

    def test_subset_returns_multi_leg(self) -> None:
        a, b = _market("a"), _market("b")
        result = check_arb_compatibility(
            a, b,
            _judgment(RelationshipType.SUBSET),
            _mapping(OutcomeMappingType.SUBSET_MAPPING),
        )
        assert result.arb_structure == ArbStructureType.MULTI_LEG_BASKET
        assert result.is_compatible
