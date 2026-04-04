"""
Adapters between upstream phase outputs and Phase 3 canonical inputs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from algorithm.Phase_2.models import CandidatePair as Phase2CandidatePair
from algorithm.Phase_2.models import MarketQuestion
from algorithm.models import CandidatePair as CanonicalCandidatePair
from algorithm.models import Market


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def phase2_question_to_market(question: MarketQuestion) -> Market:
    """
    Convert a Phase 2 MarketQuestion into the canonical Market model Phase 3 uses.

    Phase 2 only guarantees text, market, price, and free-form metadata, so this
    adapter fills the richer Market schema from metadata when available and falls
    back to a standard binary market shape otherwise.
    """
    metadata = dict(question.metadata)
    outcomes = metadata.get("outcomes") or ["Yes", "No"]

    prices = metadata.get("prices")
    if not isinstance(prices, dict):
        if len(outcomes) == 2:
            prices = {str(outcomes[0]): question.price, str(outcomes[1]): 1.0 - question.price}
        else:
            prices = {}

    orderbook = metadata.get("orderbook")
    fees = float(metadata.get("fees", 0.0))

    return Market(
        platform=question.market,
        market_id=str(metadata.get("market_id", question.id)),
        question=question.text,
        description=metadata.get("description"),
        outcomes=[str(outcome) for outcome in outcomes],
        prices={str(key): float(value) for key, value in prices.items()},
        orderbook=orderbook if isinstance(orderbook, dict) else None,
        fees=fees,
        open_time=_parse_datetime(metadata.get("open_time")),
        close_time=_parse_datetime(metadata.get("close_time")),
        resolution_rules=metadata.get("resolution_rules"),
    )


def phase2_candidate_to_canonical(candidate: Phase2CandidatePair) -> CanonicalCandidatePair:
    """Convert a Phase 2 candidate pair into the canonical Phase 3 input model."""
    return CanonicalCandidatePair(
        candidate_id=candidate.id,
        market_a=phase2_question_to_market(candidate.question_a),
        market_b=phase2_question_to_market(candidate.question_b),
        embedding_similarity=candidate.similarity_score,
        metadata={
            "phase2_pair_id": candidate.id,
            "has_potential_negation": candidate.has_potential_negation,
            "negation_tokens": list(candidate.negation_tokens),
        },
    )


def ensure_canonical_candidate(
    candidate: CanonicalCandidatePair | Phase2CandidatePair,
) -> CanonicalCandidatePair:
    """Normalize supported upstream candidate types into the canonical model."""
    if isinstance(candidate, CanonicalCandidatePair):
        return candidate
    if isinstance(candidate, Phase2CandidatePair):
        return phase2_candidate_to_canonical(candidate)
    raise TypeError(f"Unsupported candidate type for Phase 3: {type(candidate)!r}")
