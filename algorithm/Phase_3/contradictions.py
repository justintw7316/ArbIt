"""
Layer 3 — Hard Contradiction Filter.

ONLY rejects on HIGH-confidence positive evidence of mismatch. Missing
fields are always NEUTRAL — never a rejection signal. This keeps the filter
lenient so the LLM judge makes the final call.
"""

from __future__ import annotations

import re

from algorithm.Phase_3.config import get_config
from algorithm.Phase_3.models import (
    ContradictionResult,
    ExtractedFeatures,
    MarketTemplate,
    TemplateResult,
)
from algorithm.Phase_3.utils import date_gap_days

# Template pairs that are clearly incompatible (ordered; we check both orderings)
_INCOMPATIBLE_TEMPLATE_PAIRS: set[frozenset[MarketTemplate]] = {
    frozenset({MarketTemplate.BINARY_WINNER, MarketTemplate.MULTI_OUTCOME_EXHAUSTIVE}),
    frozenset({MarketTemplate.RANGE_BUCKET_MARKET, MarketTemplate.BINARY_WINNER}),
}

# Patterns that signal nomination vs general election
_NOMINATION_PATTERNS = [
    r"\bnomination\b",
    r"\bnominee\b",
    r"\bprimary\b",
    r"\bcaucus\b",
]
_GENERAL_ELECTION_PATTERNS = [
    r"\bgeneral election\b",
    r"\bpresidential election\b",
    r"\bnational election\b",
]


def _is_nomination(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _NOMINATION_PATTERNS)


def _is_general_election(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _GENERAL_ELECTION_PATTERNS)


def check_contradictions(
    features_a: ExtractedFeatures,
    features_b: ExtractedFeatures,
    template_a: TemplateResult,
    template_b: TemplateResult,
) -> ContradictionResult:
    """
    Check for hard contradictions between two markets.

    Returns ContradictionResult with hard_reject=True only when there is
    high-confidence evidence of genuine mismatch.
    """
    config = get_config()
    flags: list[str] = []
    hard_reject = False
    max_confidence: float = 0.0

    # ------------------------------------------------------------------
    # 1. Entity mismatch
    # ------------------------------------------------------------------
    entity_a = features_a.primary_entity
    entity_b = features_b.primary_entity

    if (
        entity_a
        and entity_b
        and entity_a != entity_b
        and len(entity_a) > 2
        and len(entity_b) > 2
    ):
        # Only flag if entities are clearly distinct (not substrings of each other)
        if entity_a not in entity_b and entity_b not in entity_a:
            confidence = config.entity_match_threshold
            flags.append(
                f"entity_mismatch: '{entity_a}' vs '{entity_b}' (confidence {confidence:.2f})"
            )
            if confidence >= config.entity_match_threshold:
                hard_reject = True
                max_confidence = max(max_confidence, confidence)

    # ------------------------------------------------------------------
    # 2. Incompatible template pair
    # ------------------------------------------------------------------
    pair = frozenset({template_a.primary_template, template_b.primary_template})
    if pair in _INCOMPATIBLE_TEMPLATE_PAIRS:
        if template_a.confidence >= 0.8 and template_b.confidence >= 0.8:
            flags.append(
                f"incompatible_templates: {template_a.primary_template} vs "
                f"{template_b.primary_template}"
            )
            hard_reject = True
            max_confidence = max(max_confidence, 0.9)

    # ------------------------------------------------------------------
    # 3. Date window gap
    # ------------------------------------------------------------------
    date_a = features_a.date_window_end
    date_b = features_b.date_window_end

    if date_a and date_b:
        gap = date_gap_days(date_a, date_b)
        if gap is not None and gap > config.date_tolerance_days:
            flags.append(
                f"date_gap_exceeded: {gap:.0f} days apart "
                f"(threshold {config.date_tolerance_days})"
            )
            hard_reject = True
            max_confidence = max(max_confidence, 0.85)

    # ------------------------------------------------------------------
    # 4. Threshold numeric mismatch
    # ------------------------------------------------------------------
    thresh_a = features_a.thresholds
    thresh_b = features_b.thresholds

    if thresh_a and thresh_b:
        t_a = thresh_a[0]
        t_b = thresh_b[0]
        if t_a > 0 and t_b > 0:
            ratio = abs(t_a - t_b) / max(t_a, t_b)
            if ratio > 0.05:  # > 5% difference
                flags.append(
                    f"threshold_mismatch: {t_a} vs {t_b} ({ratio:.1%} difference)"
                )
                # soft flag only — LLM decides; unit differences can cause false positives

    # ------------------------------------------------------------------
    # 5. Nomination vs general election mismatch
    # ------------------------------------------------------------------
    q_a = features_a.normalized_question
    q_b = features_b.normalized_question

    nom_a = _is_nomination(q_a)
    nom_b = _is_nomination(q_b)
    gen_a = _is_general_election(q_a)
    gen_b = _is_general_election(q_b)

    if (nom_a and gen_b) or (gen_a and nom_b):
        flags.append("nomination_vs_general_election_mismatch")
        hard_reject = True
        max_confidence = max(max_confidence, 0.92)

    return ContradictionResult(
        hard_reject=hard_reject,
        flags=flags,
        confidence=max_confidence if hard_reject else 0.0,
    )
