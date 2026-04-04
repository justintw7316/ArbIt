"""Adapters converting Phase 3 outputs into Phase 4 inputs.

Phase 3 outputs (CandidatePair, Phase3Decision) use the canonical
algorithm.models.Market type.  Phase 4 needs MarketInfo objects with
explicit yes_price / no_price fields.  This module bridges that gap.
"""

from __future__ import annotations

import logging

from algorithm.models import CandidatePair, Market
from algorithm.Phase_3.models import Phase3Decision
from algorithm.Phase_4.models import MarketInfo, MatchedPair, Platform

logger = logging.getLogger(__name__)


def _extract_yes_price(market: Market) -> float:
    """Extract YES price from a Market's prices dict."""
    for key in ("YES", "yes", "Yes"):
        if key in market.prices:
            return float(market.prices[key])
    # Fallback: first value in dict
    if market.prices:
        return float(next(iter(market.prices.values())))
    return 0.5


def _to_platform(platform_str: str) -> Platform:
    """Convert a platform string to the Platform enum, gracefully."""
    normalized = platform_str.lower().strip()
    for member in Platform:
        if member.value == normalized:
            return member
    # Partial match
    for member in Platform:
        if member.value in normalized or normalized in member.value:
            return member
    logger.warning("Unknown platform '%s' — defaulting to POLYMARKET", platform_str)
    return Platform.POLYMARKET


def _market_to_info(market: Market) -> MarketInfo:
    """Convert a canonical Market to a MarketInfo for Phase 4."""
    yes_price = _extract_yes_price(market)
    no_price = market.prices.get("NO", market.prices.get("no", round(1.0 - yes_price, 6)))
    return MarketInfo(
        platform=_to_platform(market.platform),
        market_id=market.market_id,
        yes_price=yes_price,
        no_price=float(no_price),
        close_date=market.close_time,
    )


def phase3_to_matched_pair(
    candidate: CandidatePair,
    decision: Phase3Decision,
) -> MatchedPair:
    """Convert a Phase 3 ACCEPT'd candidate + decision into a MatchedPair.

    Parameters
    ----------
    candidate : the original CandidatePair from Phase 2
    decision  : the Phase3Decision with verdict=ACCEPT
    """
    return MatchedPair(
        pair_id=candidate.candidate_id,
        market_a=_market_to_info(candidate.market_a),
        market_b=_market_to_info(candidate.market_b),
        similarity_score=candidate.embedding_similarity,
        metadata={
            "phase3_confidence": decision.confidence,
            "relationship_type": decision.relationship_type.value
            if decision.relationship_type
            else None,
            "outcome_mapping": decision.outcome_mapping.mapping_type.value
            if decision.outcome_mapping
            else None,
        },
    )


def filter_accepted(
    candidates: list[CandidatePair],
    decisions: list[Phase3Decision],
) -> list[MatchedPair]:
    """Return MatchedPair objects only for ACCEPT'd decisions.

    Parameters
    ----------
    candidates : Phase 2 candidate pairs (must be same length/order as decisions)
    decisions  : Phase 3 decisions for each candidate
    """
    from algorithm.Phase_3.models import Verdict

    if len(candidates) != len(decisions):
        raise ValueError(
            f"candidates ({len(candidates)}) and decisions ({len(decisions)}) must be same length"
        )

    matched = []
    for candidate, decision in zip(candidates, decisions):
        if decision.verdict == Verdict.ACCEPT:
            matched.append(phase3_to_matched_pair(candidate, decision))
        else:
            logger.debug(
                "Filtering out %s (verdict=%s)", candidate.candidate_id, decision.verdict.value
            )
    return matched
