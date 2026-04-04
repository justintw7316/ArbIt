"""
Layer 1 — Template Classifier.

Assigns a MarketTemplate to each market based on regex/keyword matching on
the question text. Unknown template is non-fatal.
"""

from __future__ import annotations

import re
from typing import Optional

from algorithm.models import Market
from algorithm.Phase_3.models import MarketTemplate, TemplateResult
from algorithm.Phase_3.utils import normalize_question


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[MarketTemplate, list[str], float]] = [
    # (template, list_of_regex_patterns, base_confidence)
    (
        MarketTemplate.ELECTION_EVENT,
        [
            r"\belection\b",
            r"\bvote\b.*\bpresident",
            r"\bprimary\b",
            r"\bballot\b",
            r"\belect(ed)?\b",
            r"\bpresidential\b",
            r"\bsenate race\b",
            r"\bhouse race\b",
            r"\bgovernor\b.*\belection\b",
        ],
        0.9,
    ),
    (
        MarketTemplate.APPROVAL_EVENT,
        [
            r"\bapprove[d]?\b",
            r"\bapproval\b",
            r"\bpass(ed)?\b.*\bbill\b",
            r"\bsigned into law\b",
            r"\blegislation\b",
            r"\bconfirm(ed|ation)?\b",
            r"\bratif(y|ied|ication)\b",
        ],
        0.85,
    ),
    (
        MarketTemplate.SPORTS_RESULT,
        [
            r"\bwin\b.*\bgame\b",
            r"\bchampionship\b",
            r"\bsuperbowl\b",
            r"\bsuper bowl\b",
            r"\bnba\b",
            r"\bnfl\b",
            r"\bmlb\b",
            r"\bnhl\b",
            r"\bworld series\b",
            r"\bworld cup\b",
            r"\bplayoffs?\b",
            r"\bfinals?\b.*\b(win|champion)\b",
            r"\bmatch\b.*\b(win|lose)\b",
        ],
        0.9,
    ),
    (
        MarketTemplate.THRESHOLD_EVENT,
        [
            r"\breach\b.*\b\$?[\d,]+",
            r"\bexceed[s]?\b",
            r"\babove\b.*\b\$?[\d,]+",
            r"\bbelow\b.*\b\$?[\d,]+",
            r"\bat least\b.*\b[\d,]+",
            r"\bmore than\b.*\b[\d,]+",
            r"\b(price|rate|level)\b.*\b[\d,]+",
            r"\b[\d,]+\b.*\b(billion|million|trillion)\b",
        ],
        0.8,
    ),
    (
        MarketTemplate.BY_DATE_EVENT,
        [
            r"\bby\b.*\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
            r"\bby\b.*\b20\d{2}\b",
            r"\bby end of\b",
            r"\bbefore\b.*\b20\d{2}\b",
            r"\bprior to\b",
            r"\bdeadline\b",
        ],
        0.8,
    ),
    (
        MarketTemplate.RANGE_BUCKET_MARKET,
        [
            r"\bbetween\b.*\band\b.*\b[\d,]+",
            r"\brange\b",
            r"\bbucket\b",
            r"[\d,]+\s*[-–]\s*[\d,]+",
            r"\binterval\b",
        ],
        0.75,
    ),
    (
        MarketTemplate.MARGIN_MARKET,
        [
            r"\bmargin\b",
            r"\bspread\b",
            r"\bpoints?\b.*\b(win|lead|ahead)\b",
            r"\bby more than\b.*\bpoints?\b",
        ],
        0.8,
    ),
    (
        MarketTemplate.MULTI_OUTCOME_EXHAUSTIVE,
        [
            r"\bwhich\b.*\bwill\b.*\b(first|win|be)\b",
            r"\bwho will\b",
            r"\bwhich (team|country|candidate|party|company)\b",
        ],
        0.7,
    ),
    (
        MarketTemplate.BINARY_WINNER,
        [
            r"\bwill\b.*\b(win|lose|happen|occur|be elected|be appointed|be confirmed)\b",
            r"\b(yes|no)\b.*\bmarket\b",
            r"\bwill .* (succeed|fail|resign|pass away|be impeached)\b",
        ],
        0.7,
    ),
]


def _count_matches(text: str, patterns: list[str]) -> tuple[int, list[str]]:
    matched: list[str] = []
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            matched.append(pat)
    return len(matched), matched


def classify_market(market: Market) -> TemplateResult:
    """
    Classify a single market into a MarketTemplate.
    Returns the primary (and optional secondary) template with confidence.
    """
    text = normalize_question(market.question)
    if market.description:
        text = text + " " + normalize_question(market.description)

    scores: list[tuple[MarketTemplate, float, list[str]]] = []

    for template, patterns, base_conf in _PATTERNS:
        count, matched = _count_matches(text, patterns)
        if count > 0:
            # Scale confidence by match density (cap at base_conf)
            conf = min(base_conf, base_conf * (0.5 + 0.5 * min(count, 3) / 3))
            scores.append((template, conf, matched))

    # Also use outcome count heuristic
    if len(market.outcomes) > 3:
        scores.append((MarketTemplate.MULTI_OUTCOME_EXHAUSTIVE, 0.6, ["outcome_count > 3"]))

    if not scores:
        return TemplateResult(
            market_id=market.market_id,
            primary_template=MarketTemplate.UNKNOWN,
            confidence=0.5,
            matched_patterns=[],
        )

    scores.sort(key=lambda x: x[1], reverse=True)
    primary_template, primary_conf, primary_patterns = scores[0]

    secondary: Optional[MarketTemplate] = None
    if len(scores) > 1 and scores[1][1] >= 0.5:
        secondary = scores[1][0]

    return TemplateResult(
        market_id=market.market_id,
        primary_template=primary_template,
        secondary_template=secondary,
        confidence=primary_conf,
        matched_patterns=primary_patterns[:5],
    )


def classify_pair(
    market_a: Market, market_b: Market
) -> tuple[TemplateResult, TemplateResult]:
    """Classify both markets in a pair."""
    return classify_market(market_a), classify_market(market_b)
