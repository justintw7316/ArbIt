"""
Layer 4 — Reranker.

Provides a relevance score (0–1) for a market pair. The score is used for
confidence weighting but never gates LLM invocation — LLM always runs on
survivors of the contradiction filter.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from algorithm.models import Market
from algorithm.Phase_3.models import RerankerResult
from algorithm.Phase_3.utils import date_gap_days, extract_dates, token_overlap


class BaseReranker(ABC):
    @abstractmethod
    def score(self, market_a: Market, market_b: Market) -> RerankerResult:
        ...


class MockReranker(BaseReranker):
    """
    Weighted average of:
      - embedding-similarity proxy (token overlap on question text): 50%
      - date proximity: 30%
      - outcome label overlap: 20%
    """

    def score(self, market_a: Market, market_b: Market) -> RerankerResult:
        # Token overlap on question text
        text_score = token_overlap(market_a.question, market_b.question)

        # Date proximity: 1.0 if same date, 0.0 if ≥ 90 days apart
        date_score = self._date_proximity(market_a, market_b)

        # Outcome label overlap
        outcome_score = self._outcome_overlap(market_a, market_b)

        total = 0.5 * text_score + 0.3 * date_score + 0.2 * outcome_score
        total = max(0.0, min(1.0, total))

        return RerankerResult(
            score=total,
            components={
                "text_overlap": text_score,
                "date_proximity": date_score,
                "outcome_overlap": outcome_score,
            },
            reranker_type="mock",
        )

    def _date_proximity(self, market_a: Market, market_b: Market) -> float:
        dates_a = extract_dates(market_a.question + " " + (market_a.description or ""))
        dates_b = extract_dates(market_b.question + " " + (market_b.description or ""))

        # Also use close_time if present
        if market_a.close_time:
            dates_a.append(market_a.close_time.strftime("%Y-%m-%d"))
        if market_b.close_time:
            dates_b.append(market_b.close_time.strftime("%Y-%m-%d"))

        if not dates_a or not dates_b:
            return 0.5  # Neutral when no dates found

        # Use last date (closest to resolution) from each
        gap = date_gap_days(dates_a[-1], dates_b[-1])
        if gap is None:
            return 0.5
        # Decay over 90 days
        return max(0.0, 1.0 - gap / 90.0)

    def _outcome_overlap(self, market_a: Market, market_b: Market) -> float:
        set_a = {o.lower().strip() for o in market_a.outcomes}
        set_b = {o.lower().strip() for o in market_b.outcomes}
        # Also check complement: YES/NO are always complements
        if set_a and set_b:
            intersection = set_a & set_b
            union = set_a | set_b
            direct = len(intersection) / len(union)
            # Check inverted complement
            complements = {
                "yes": "no", "no": "yes",
                "true": "false", "false": "true",
            }
            inverted = {complements.get(o, o) for o in set_a}
            inv_intersection = inverted & set_b
            inv_score = len(inv_intersection) / len(union)
            return max(direct, inv_score)
        return 0.5


class OpenAIReranker(BaseReranker):
    """
    Stub reranker using OpenAI text-embedding-3-small cosine similarity.
    Falls back to MockReranker if API key is not set.
    """

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._mock = MockReranker()

    def score(self, market_a: Market, market_b: Market) -> RerankerResult:
        if not self._api_key:
            result = self._mock.score(market_a, market_b)
            return RerankerResult(
                score=result.score,
                components=result.components,
                reranker_type="openai_stub_fallback",
            )
        # Real embedding call (stub — would use openai.embeddings.create)
        # Keeping as stub to avoid blocking on API key availability
        result = self._mock.score(market_a, market_b)
        return RerankerResult(
            score=result.score,
            components=result.components,
            reranker_type="openai_stub",
        )


def build_reranker(reranker_type: str = "mock", api_key: str = "") -> BaseReranker:
    if reranker_type == "openai":
        return OpenAIReranker(api_key=api_key)
    return MockReranker()
