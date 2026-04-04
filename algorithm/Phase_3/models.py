"""
Phase 3 specific data models: enums and Pydantic schemas for all layer outputs.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MarketTemplate(str, Enum):
    BINARY_WINNER = "binary_winner"
    THRESHOLD_EVENT = "threshold_event"
    BY_DATE_EVENT = "by_date_event"
    SPORTS_RESULT = "sports_result"
    APPROVAL_EVENT = "approval_event"
    ELECTION_EVENT = "election_event"
    MARGIN_MARKET = "margin_market"
    RANGE_BUCKET_MARKET = "range_bucket_market"
    MULTI_OUTCOME_EXHAUSTIVE = "multi_outcome_exhaustive"
    UNKNOWN = "unknown"


class RelationshipType(str, Enum):
    EQUIVALENT = "equivalent"
    COMPLEMENT = "complement"
    SUBSET = "subset"
    SUPERSET = "superset"
    RELATED_NOT_ARB = "related_but_not_arb_compatible"
    UNRELATED = "unrelated"


class OutcomeMappingType(str, Enum):
    DIRECT = "direct"  # YES_A ↔ YES_B
    INVERTED = "inverted"  # YES_A ↔ NO_B
    COMPLEMENT_PAIR = "complement_pair"
    SUBSET_MAPPING = "subset_mapping"
    MULTI_LEG = "multi_leg"
    UNMAPPABLE = "unmappable"


class ArbStructureType(str, Enum):
    BINARY_PAIR = "binary_pair"
    COMPLEMENT_BASKET = "complement_basket"
    MULTI_LEG_BASKET = "multi_leg_basket"
    NOT_ARB = "not_arb"


class Verdict(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


# ---------------------------------------------------------------------------
# Layer outputs
# ---------------------------------------------------------------------------


class TemplateResult(BaseModel):
    market_id: str
    primary_template: MarketTemplate
    secondary_template: MarketTemplate | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    matched_patterns: list[str] = Field(default_factory=list)


class ExtractedFeatures(BaseModel):
    """Soft NLP features extracted from a single market question + description."""

    market_id: str
    entities: list[str] = Field(default_factory=list)
    primary_entity: str | None = None
    dates: list[str] = Field(default_factory=list)
    date_window_start: str | None = None
    date_window_end: str | None = None
    thresholds: list[float] = Field(default_factory=list)
    comparators: list[str] = Field(default_factory=list)  # ">", "<", ">=", etc.
    polarity: str | None = None  # "positive" | "negative" | None
    jurisdiction: str | None = None
    resolution_source_hints: list[str] = Field(default_factory=list)
    normalized_question: str = ""


class ContradictionResult(BaseModel):
    hard_reject: bool
    flags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class RerankerResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    components: dict[str, float] = Field(default_factory=dict)
    reranker_type: str = "mock"


class LLMJudgment(BaseModel):
    verdict: Verdict
    relationship_type: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    outcome_hints: dict[str, str] = Field(default_factory=dict)
    raw_response: str = ""


class OutcomeMappingResult(BaseModel):
    mapping_type: OutcomeMappingType
    mappings: dict[str, str] = Field(default_factory=dict)  # outcome_a -> outcome_b
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    notes: str = ""


class ArbCompatibilityResult(BaseModel):
    arb_structure: ArbStructureType
    is_compatible: bool
    rejection_reason: str | None = None
    legs: list[dict[str, Any]] = Field(default_factory=list)


class Phase3Decision(BaseModel):
    """Final output per candidate from Phase 3."""

    candidate_id: str
    verdict: Verdict
    reason: str
    contradiction_flags: list[str] = Field(default_factory=list)
    extracted_features_a: ExtractedFeatures | None = None
    extracted_features_b: ExtractedFeatures | None = None
    template_labels: list[TemplateResult] = Field(default_factory=list)
    reranker_score: float = 0.0
    llm_verdict: LLMJudgment | None = None
    relationship_type: RelationshipType = RelationshipType.UNRELATED
    outcome_mapping: OutcomeMappingResult | None = None
    arb_compatibility: ArbCompatibilityResult | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    processing_time_ms: float = 0.0
    error: str | None = None
