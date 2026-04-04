"""
Layer 6b — Arb Compatibility Check.

Determines whether a validated pair can form a clean arbitrage basket
for Phase 4. Rejects structurally incompatible combinations.
"""

from __future__ import annotations

from algorithm.models import Market
from algorithm.Phase_3.models import (
    ArbCompatibilityResult,
    ArbStructureType,
    LLMJudgment,
    OutcomeMappingResult,
    OutcomeMappingType,
    RelationshipType,
    Verdict,
)


def check_arb_compatibility(
    market_a: Market,
    market_b: Market,
    judgment: LLMJudgment,
    outcome_mapping: OutcomeMappingResult,
) -> ArbCompatibilityResult:
    """
    Determine if the market pair can form an arbitrage basket.

    Rejects:
    - RELATED_NOT_ARB or UNRELATED relationship types
    - Exhaustive multi-outcome groups with incomplete outcome coverage
    - Unmappable outcomes with no LLM hints
    """
    rel = judgment.relationship_type

    # Immediately reject non-arb relationships
    if rel == RelationshipType.UNRELATED:
        return ArbCompatibilityResult(
            arb_structure=ArbStructureType.NOT_ARB,
            is_compatible=False,
            rejection_reason="Relationship type is 'unrelated'",
        )

    if rel == RelationshipType.RELATED_NOT_ARB:
        return ArbCompatibilityResult(
            arb_structure=ArbStructureType.NOT_ARB,
            is_compatible=False,
            rejection_reason="Relationship type is 'related_but_not_arb_compatible'",
        )

    # Unmappable outcomes with no hints from LLM
    if (
        outcome_mapping.mapping_type == OutcomeMappingType.UNMAPPABLE
        and not judgment.outcome_hints
    ):
        return ArbCompatibilityResult(
            arb_structure=ArbStructureType.NOT_ARB,
            is_compatible=False,
            rejection_reason="Cannot map outcomes between markets",
        )

    # Multi-leg basket (subset/superset) — check before binary pair
    if rel in (RelationshipType.SUBSET, RelationshipType.SUPERSET):
        return ArbCompatibilityResult(
            arb_structure=ArbStructureType.MULTI_LEG_BASKET,
            is_compatible=True,
            rejection_reason=None,
            legs=[],
        )

    # Complement basket (one market's YES pairs with another's NO, etc.)
    if rel == RelationshipType.COMPLEMENT and outcome_mapping.mappings:
        legs = _build_complement_legs(market_a, market_b, outcome_mapping)
        return ArbCompatibilityResult(
            arb_structure=ArbStructureType.COMPLEMENT_BASKET,
            is_compatible=True,
            legs=legs,
        )

    # Binary pair (both markets have exactly 2 outcomes)
    if len(market_a.outcomes) == 2 and len(market_b.outcomes) == 2:
        legs = _build_binary_legs(market_a, market_b, outcome_mapping)
        return ArbCompatibilityResult(
            arb_structure=ArbStructureType.BINARY_PAIR,
            is_compatible=True,
            legs=legs,
        )

    # Equivalent with multi-outcome — check coverage
    if rel == RelationshipType.EQUIVALENT:
        if len(market_a.outcomes) > 2 and len(market_b.outcomes) > 2:
            covered = len(outcome_mapping.mappings)
            needed = len(market_a.outcomes)
            if covered < needed:
                return ArbCompatibilityResult(
                    arb_structure=ArbStructureType.NOT_ARB,
                    is_compatible=False,
                    rejection_reason=(
                        f"Exhaustive multi-outcome: only {covered}/{needed} outcomes mapped"
                    ),
                )
        legs = _build_binary_legs(market_a, market_b, outcome_mapping)
        return ArbCompatibilityResult(
            arb_structure=ArbStructureType.BINARY_PAIR,
            is_compatible=True,
            legs=legs,
        )

    return ArbCompatibilityResult(
        arb_structure=ArbStructureType.NOT_ARB,
        is_compatible=False,
        rejection_reason=f"Unhandled relationship type: {rel}",
    )


def _build_binary_legs(
    market_a: Market,
    market_b: Market,
    outcome_mapping: OutcomeMappingResult,
) -> list[dict[str, object]]:
    legs: list[dict[str, object]] = []
    for outcome_a, outcome_b in outcome_mapping.mappings.items():
        price_a = market_a.prices.get(outcome_a, 0.0)
        price_b = market_b.prices.get(outcome_b, 0.0)
        legs.append({
            "platform_a": market_a.platform,
            "market_id_a": market_a.market_id,
            "outcome_a": outcome_a,
            "price_a": price_a,
            "platform_b": market_b.platform,
            "market_id_b": market_b.market_id,
            "outcome_b": outcome_b,
            "price_b": price_b,
            "combined_price": price_a + price_b,
        })
    return legs


def _build_complement_legs(
    market_a: Market,
    market_b: Market,
    outcome_mapping: OutcomeMappingResult,
) -> list[dict[str, object]]:
    # For complement: bet YES on A and YES on B (they can't both win)
    legs: list[dict[str, object]] = []
    for outcome_a, outcome_b in outcome_mapping.mappings.items():
        price_a = market_a.prices.get(outcome_a, 0.0)
        price_b = market_b.prices.get(outcome_b, 0.0)
        legs.append({
            "platform_a": market_a.platform,
            "market_id_a": market_a.market_id,
            "outcome_a": outcome_a,
            "price_a": price_a,
            "platform_b": market_b.platform,
            "market_id_b": market_b.market_id,
            "outcome_b": outcome_b,
            "price_b": price_b,
            "combined_price": price_a + price_b,
            "leg_type": "complement",
        })
    return legs
