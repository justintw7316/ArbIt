"""Data models for the vector database."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VectorRecord:
    """A single record stored in the vector database."""

    id: str
    vector: List[float]
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    namespace: str = "default"

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("VectorRecord.id must be a non-empty string")
        if not isinstance(self.vector, list):
            raise TypeError("VectorRecord.vector must be a list of floats")


@dataclass
class QueryResult:
    """A single result from a vector similarity query."""

    record: VectorRecord
    score: float
    rank: int

    def __repr__(self) -> str:
        text_preview = (self.record.text[:60] + "...") if len(self.record.text) > 60 else self.record.text
        return f"QueryResult(rank={self.rank}, score={self.score:.4f}, text={text_preview!r})"


@dataclass
class MarketQuestion:
    """A question from a prediction market (interface from step 1 scraper).

    Attributes:
        id: Unique identifier within this market (from the API).
        text: The question text, e.g. "Will Trump win the 2024 election?".
        market: Source market name, e.g. "polymarket", "kalshi", "manifold".
        price: Current implied probability [0.0, 1.0].
        metadata: Additional fields from the API (volume, liquidity, close_time, etc.).
    """

    id: str
    text: str
    market: str
    price: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None  # pre-computed embedding, loaded from MongoDB

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("MarketQuestion.id must be a non-empty string")
        if not self.text or not self.text.strip():
            raise ValueError("MarketQuestion.text must be a non-empty string")
        if not self.market:
            raise ValueError("MarketQuestion.market must be a non-empty string")
        if not (0.0 <= self.price <= 1.0):
            raise ValueError(f"MarketQuestion.price must be in [0, 1], got {self.price}")


@dataclass
class CandidatePair:
    """A candidate arbitrage pair to be verified by step 3 (LLM verification).

    Two questions from different markets with high semantic similarity are
    potential arbitrage opportunities. The has_potential_negation flag is set
    when one question appears to semantically negate the other — step 3 must
    verify whether the questions are truly equivalent or inverted.

    Attributes:
        id: Deterministic pair ID (hash of the two question IDs).
        question_a: Question from market A.
        question_b: Question from market B.
        similarity_score: Cosine similarity [0.0, 1.0]; higher = more similar.
        has_potential_negation: True if asymmetric negation tokens detected.
        negation_tokens: The specific tokens that triggered the negation flag.
    """

    id: str
    question_a: MarketQuestion
    question_b: MarketQuestion
    similarity_score: float
    has_potential_negation: bool = False
    negation_tokens: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        preview_a = self.question_a.text[:50]
        preview_b = self.question_b.text[:50]
        neg = f", negation={self.negation_tokens}" if self.has_potential_negation else ""
        return (
            f"CandidatePair(score={self.similarity_score:.4f}{neg}, "
            f"a=[{self.question_a.market}] {preview_a!r}, "
            f"b=[{self.question_b.market}] {preview_b!r})"
        )
