"""
Layer 2 — Soft NLP Feature Extractor.

Extracts entities, dates, thresholds, comparators, polarity, jurisdiction, and
resolution source hints from market text using regex + stdlib. No spaCy dep.
All fields are Optional — missing fields are neutral, never a rejection signal.
"""

from __future__ import annotations

import re

from algorithm.models import Market
from algorithm.Phase_3.models import ExtractedFeatures
from algorithm.Phase_3.utils import (
    extract_comparators,
    extract_dates,
    extract_thresholds,
    normalize_entity,
    normalize_question,
)

# ---------------------------------------------------------------------------
# Entity extraction patterns
# ---------------------------------------------------------------------------

# Named-entity-like patterns: capitalized proper nouns, known prefixes
_NE_PATTERNS = [
    # Ticker symbols: $BTC, BTC, ETH etc.
    r"\$([A-Z]{2,6})\b",
    # Country / org names (2+ capitalized words in sequence)
    r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)+)\b",
    # Single-word proper nouns with context clues (preceded by "the", "of", etc.)
    r"(?:president|senator|governor|secretary|ceo|founder|candidate)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
]

# Jurisdiction markers
_JURISDICTION_PATTERNS = [
    r"\b(United States|U\.S\.|USA|US)\b",
    r"\b(United Kingdom|UK|U\.K\.)\b",
    r"\b(European Union|EU)\b",
    r"\b(China|Japan|India|Russia|Germany|France|Brazil)\b",
    r"\b(California|Texas|New York|Florida|Illinois)\b",
    r"\b(Congress|Senate|House of Representatives|Supreme Court)\b",
    r"\b(Federal Reserve|Fed|ECB|IMF|World Bank)\b",
]

# Resolution source hints
_RESOLUTION_PATTERNS = [
    r"\baccording to\s+([A-Z][^\.,]{2,40})",
    r"\breported by\s+([A-Z][^\.,]{2,40})",
    r"\b(AP|Reuters|Bloomberg|CNN|BBC|NYT|Washington Post|Associated Press)\b",
    r"\b(official results?|official announcement|official statement)\b",
    r"\b(closing price|last traded price)\b",
    r"\b(polymarket|kalshi|manifold|prediction market)\b",
]

# Polarity / negation
_POSITIVE_PATTERNS = [r"\bwill\b", r"\bsucceed\b", r"\bwin\b", r"\bpass\b", r"\bapprove\b"]
_NEGATIVE_PATTERNS = [r"\bwill not\b", r"\bwon'?t\b", r"\bfail\b", r"\bno\b\s+\b"]


# Common English words that appear capitalized at start of sentence but are not entities
_NON_ENTITY_WORDS = frozenset({
    "will", "would", "could", "should", "does", "did", "has", "have", "had",
    "is", "are", "was", "were", "be", "been", "being",
    "the", "a", "an", "this", "that", "these", "those",
    "if", "when", "whether", "what", "which", "who", "whose", "how",
    "by", "in", "on", "at", "of", "for", "to", "from", "with",
    "and", "or", "but", "not", "no", "yes",
    "before", "after", "during", "until", "since",
})


def _extract_entities(text: str) -> list[str]:
    """Extract and normalize candidate entity names."""
    raw: list[str] = []

    for pat in _NE_PATTERNS:
        for m in re.finditer(pat, text):
            entity = m.group(1) if m.lastindex else m.group(0)
            raw.append(entity.strip())

    # Also grab quoted strings as potential entities
    for m in re.finditer(r'"([^"]{2,50})"', text):
        raw.append(m.group(1).strip())

    normalized = [normalize_entity(e) for e in raw if len(e) > 1]

    # Filter out entities whose first word is a common non-entity English word
    def _is_valid_entity(e: str) -> bool:
        first_word = e.split()[0] if e.split() else e
        return first_word.lower() not in _NON_ENTITY_WORDS

    # Deduplicate preserving order, filter non-entities
    seen: set[str] = set()
    result: list[str] = []
    for e in normalized:
        if e not in seen and len(e) > 1 and _is_valid_entity(e):
            seen.add(e)
            result.append(e)
    return result[:10]  # cap at 10


def _extract_jurisdiction(text: str) -> str | None:
    for pat in _JURISDICTION_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return normalize_entity(m.group(0))
    return None


def _extract_resolution_hints(text: str) -> list[str]:
    hints: list[str] = []
    for pat in _RESOLUTION_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            hint = m.group(1) if m.lastindex else m.group(0)
            hints.append(hint.strip().lower())
    return list(dict.fromkeys(hints))


def _detect_polarity(text: str) -> str | None:
    neg = any(re.search(p, text, re.IGNORECASE) for p in _NEGATIVE_PATTERNS)
    pos = any(re.search(p, text, re.IGNORECASE) for p in _POSITIVE_PATTERNS)
    if neg:
        return "negative"
    if pos:
        return "positive"
    return None


def extract_features(market: Market) -> ExtractedFeatures:
    """Extract soft NLP features from a single market."""
    full_text = market.question
    if market.description:
        full_text = full_text + " " + market.description
    if market.resolution_rules:
        full_text = full_text + " " + market.resolution_rules

    entities = _extract_entities(full_text)
    primary_entity = entities[0] if entities else None

    dates = extract_dates(full_text)
    date_start: str | None = None
    date_end: str | None = None
    if len(dates) == 1:
        date_end = dates[0]
    elif len(dates) >= 2:
        date_start = dates[0]
        date_end = dates[-1]

    thresholds = extract_thresholds(full_text)
    comparators = extract_comparators(full_text)
    polarity = _detect_polarity(market.question)
    jurisdiction = _extract_jurisdiction(full_text)
    resolution_hints = _extract_resolution_hints(full_text)
    normalized_q = normalize_question(market.question)

    return ExtractedFeatures(
        market_id=market.market_id,
        entities=entities,
        primary_entity=primary_entity,
        dates=dates,
        date_window_start=date_start,
        date_window_end=date_end,
        thresholds=thresholds,
        comparators=comparators,
        polarity=polarity,
        jurisdiction=jurisdiction,
        resolution_source_hints=resolution_hints,
        normalized_question=normalized_q,
    )
