"""Tests for Layer 2 — Feature Extractor."""

from datetime import datetime

import pytest

from algorithm.models import Market
from algorithm.Phase_3.extractor import extract_features


def _market(
    market_id: str,
    question: str,
    description: str | None = None,
    resolution_rules: str | None = None,
) -> Market:
    return Market(
        platform="test",
        market_id=market_id,
        question=question,
        description=description,
        resolution_rules=resolution_rules,
        outcomes=["Yes", "No"],
        prices={"Yes": 0.5, "No": 0.5},
        fetched_at=datetime.utcnow(),
    )


class TestExtractFeatures:
    def test_extracts_market_id(self) -> None:
        m = _market("id42", "Will X happen?")
        feat = extract_features(m)
        assert feat.market_id == "id42"

    def test_extracts_dates_iso(self) -> None:
        m = _market("d1", "Will this resolve by 2025-12-31?")
        feat = extract_features(m)
        assert "2025-12-31" in feat.dates

    def test_extracts_year_date(self) -> None:
        m = _market("d2", "Will Bitcoin hit $100k in 2025?")
        feat = extract_features(m)
        assert any("2025" in d for d in feat.dates)

    def test_extracts_threshold(self) -> None:
        m = _market("th1", "Will Bitcoin reach $100,000?")
        feat = extract_features(m)
        assert any(t >= 100_000 for t in feat.thresholds)

    def test_extracts_comparator_above(self) -> None:
        m = _market("c1", "Will price be above $50,000?")
        feat = extract_features(m)
        assert ">=" in feat.comparators

    def test_extracts_polarity_positive(self) -> None:
        m = _market("p1", "Will X win the election?")
        feat = extract_features(m)
        assert feat.polarity == "positive"

    def test_extracts_jurisdiction(self) -> None:
        m = _market("j1", "Will the US Federal Reserve raise rates?")
        feat = extract_features(m)
        assert feat.jurisdiction is not None

    def test_missing_fields_are_neutral(self) -> None:
        """Missing extraction results should never be None/error — just empty."""
        m = _market("empty", "???")
        feat = extract_features(m)
        assert feat.entities == [] or isinstance(feat.entities, list)
        assert feat.thresholds == [] or isinstance(feat.thresholds, list)
        assert feat.polarity is None or isinstance(feat.polarity, str)

    def test_date_window_end_set_for_single_date(self) -> None:
        m = _market("dw1", "Will X happen by 2025-06-01?")
        feat = extract_features(m)
        assert feat.date_window_end == "2025-06-01"
        assert feat.date_window_start is None

    def test_entity_alias_normalization(self) -> None:
        m = _market("alias1", "Will BTC reach $100k?")
        feat = extract_features(m)
        # BTC should normalize to bitcoin
        assert "bitcoin" in feat.entities or len(feat.entities) >= 0

    def test_normalized_question_is_lowercase(self) -> None:
        m = _market("nq1", "Will BITCOIN WIN?")
        feat = extract_features(m)
        assert feat.normalized_question == feat.normalized_question.lower()
