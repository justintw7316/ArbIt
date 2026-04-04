"""
Layer 6a — Outcome Mapping.

Determines how outcomes of market_a map to outcomes of market_b based on
the LLM relationship type and outcome labels.
"""

from __future__ import annotations

from algorithm.models import Market
from algorithm.Phase_3.models import (
    LLMJudgment,
    OutcomeMappingResult,
    OutcomeMappingType,
    RelationshipType,
)

_POSITIVE_LABELS = {"yes", "true", "win", "will", "above", "over", "higher"}
_NEGATIVE_LABELS = {"no", "false", "lose", "won't", "below", "under", "lower"}


def _classify_outcome(label: str) -> str:
    """Classify an outcome label as 'positive' or 'negative'."""
    normalized = label.lower().strip()
    if any(pos in normalized for pos in _POSITIVE_LABELS):
        return "positive"
    if any(neg in normalized for neg in _NEGATIVE_LABELS):
        return "negative"
    return "unknown"


def _binary_mapping(
    market_a: Market,
    market_b: Market,
    inverted: bool = False,
) -> dict[str, str]:
    """Build a simple YES/NO or POSITIVE/NEGATIVE mapping for binary markets."""
    if len(market_a.outcomes) != 2 or len(market_b.outcomes) != 2:
        return {}

    # Sort outcomes: positive first
    def sort_key(o: str) -> int:
        return 0 if _classify_outcome(o) == "positive" else 1

    a_sorted = sorted(market_a.outcomes, key=sort_key)
    b_sorted = sorted(market_b.outcomes, key=sort_key)

    if inverted:
        return {a_sorted[0]: b_sorted[1], a_sorted[1]: b_sorted[0]}
    return {a_sorted[0]: b_sorted[0], a_sorted[1]: b_sorted[1]}


def determine_outcome_mapping(
    market_a: Market,
    market_b: Market,
    judgment: LLMJudgment,
) -> OutcomeMappingResult:
    """
    Determine the outcome mapping type and specific mappings.
    Uses LLM relationship_type and outcome_hints as primary signals.
    """
    rel = judgment.relationship_type

    # Use LLM-provided hints if available
    if judgment.outcome_hints:
        return OutcomeMappingResult(
            mapping_type=OutcomeMappingType.DIRECT,
            mappings=dict(judgment.outcome_hints),
            confidence=judgment.confidence,
            notes="LLM-provided outcome hints",
        )

    # Equivalent binary pair: YES_A ↔ YES_B
    if rel == RelationshipType.EQUIVALENT:
        mappings = _binary_mapping(market_a, market_b, inverted=False)
        if mappings:
            return OutcomeMappingResult(
                mapping_type=OutcomeMappingType.DIRECT,
                mappings=mappings,
                confidence=judgment.confidence,
                notes="Equivalent binary markets — direct mapping",
            )
        # Multi-outcome: try to match by index
        if market_a.outcomes and market_b.outcomes:
            mappings = {
                a: b
                for a, b in zip(market_a.outcomes, market_b.outcomes)
            }
            return OutcomeMappingResult(
                mapping_type=OutcomeMappingType.DIRECT,
                mappings=mappings,
                confidence=judgment.confidence * 0.8,
                notes="Equivalent markets — index-matched outcomes",
            )

    # Complement pair: YES_A ↔ NO_B
    if rel == RelationshipType.COMPLEMENT:
        mappings = _binary_mapping(market_a, market_b, inverted=True)
        if mappings:
            return OutcomeMappingResult(
                mapping_type=OutcomeMappingType.INVERTED,
                mappings=mappings,
                confidence=judgment.confidence,
                notes="Complement markets — inverted mapping",
            )

    # Subset/superset
    if rel in (RelationshipType.SUBSET, RelationshipType.SUPERSET):
        return OutcomeMappingResult(
            mapping_type=OutcomeMappingType.SUBSET_MAPPING,
            mappings={},
            confidence=judgment.confidence * 0.7,
            notes=f"{rel} relationship — manual mapping required",
        )

    # Fallback: unmappable
    return OutcomeMappingResult(
        mapping_type=OutcomeMappingType.UNMAPPABLE,
        mappings={},
        confidence=0.0,
        notes=f"Cannot map outcomes for relationship type: {rel}",
    )
