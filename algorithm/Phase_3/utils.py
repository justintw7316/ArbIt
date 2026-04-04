"""
Shared text normalization and date parsing helpers for Phase 3.
"""

from __future__ import annotations

import re
import string
from datetime import datetime, date
from typing import Optional

# ---------------------------------------------------------------------------
# Entity alias normalization
# ---------------------------------------------------------------------------

_ENTITY_ALIASES: dict[str, str] = {
    # People
    "biden": "joe biden",
    "trump": "donald trump",
    "harris": "kamala harris",
    "obama": "barack obama",
    "elon": "elon musk",
    # Crypto
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "xrp": "ripple",
    "doge": "dogecoin",
    # Common abbreviations
    "us": "united states",
    "usa": "united states",
    "uk": "united kingdom",
    "eu": "european union",
    "fed": "federal reserve",
    "sec": "securities and exchange commission",
    "fda": "food and drug administration",
    "gop": "republican party",
}


def normalize_entity(entity: str) -> str:
    """Lowercase, strip punctuation, apply known aliases."""
    text = entity.lower().strip()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    return _ENTITY_ALIASES.get(text, text)


def normalize_question(text: str) -> str:
    """Lowercase and normalize whitespace for comparison."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    # ISO
    (r"\b(\d{4})-(\d{2})-(\d{2})\b", "%Y-%m-%d"),
    # US formats
    (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", "%m/%d/%Y"),
    (r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", "%m-%d-%Y"),
    # Written out
    (
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),?\s+(\d{4})\b",
        "%B %d %Y",
    ),
    (
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\.?\s+(\d{1,2}),?\s+(\d{4})\b",
        "%b %d %Y",
    ),
    # Year + quarter
    (r"\bQ([1-4])\s+(\d{4})\b", "quarter"),
]

# Patterns that resolve to specific dates (not just year)
_END_OF_YEAR_PATTERN = re.compile(
    r"\bend of\s+(20\d{2})\b|\bby\s+end\s+of\s+(20\d{2})\b", re.IGNORECASE
)
_BEFORE_YEAR_PATTERN = re.compile(
    r"\bbefore\s+(20\d{2})\b|\bprior to\s+(20\d{2})\b", re.IGNORECASE
)
# Year-only (used last, only when no specific date for that year found)
_YEAR_ONLY_PATTERN = re.compile(r"\b(20\d{2})\b")

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def extract_dates(text: str) -> list[str]:
    """Extract date strings from text. Returns normalized ISO-like strings.

    Priority order:
    1. Specific dates (ISO, US, written-out month) — most reliable
    2. Quarter dates
    3. "end of YYYY" / "by end of YYYY" → YYYY-12-31
    4. "before YYYY" / "prior to YYYY" → (YYYY-1)-12-31
    5. Year-only — only included when no specific date for that year exists
    """
    specific: list[str] = []  # dates with explicit month/day
    specific_years: set[str] = set()

    for pat, fmt in _DATE_PATTERNS:
        if fmt == "quarter":
            for m in re.finditer(pat, text, re.IGNORECASE):
                q, year = int(m.group(1)), int(m.group(2))
                month = (q - 1) * 3 + 1
                d = f"{year}-{month:02d}-01"
                specific.append(d)
                specific_years.add(str(year))
        elif "B" in fmt or "b" in fmt:
            for m in re.finditer(pat, text, re.IGNORECASE):
                month_str = m.group(1).lower().rstrip(".")
                month = _MONTH_MAP.get(month_str)
                if month:
                    day = int(m.group(2))
                    year = int(m.group(3))
                    d = f"{year}-{month:02d}-{day:02d}"
                    specific.append(d)
                    specific_years.add(str(year))
        else:
            for m in re.finditer(pat, text):
                try:
                    parts = m.group(0)
                    dt = datetime.strptime(parts, fmt)
                    d = dt.strftime("%Y-%m-%d")
                    specific.append(d)
                    specific_years.add(str(dt.year))
                except ValueError:
                    pass

    # "end of YYYY" / "by end of YYYY" → YYYY-12-31
    for m in _END_OF_YEAR_PATTERN.finditer(text):
        year_str = m.group(1) or m.group(2)
        d = f"{year_str}-12-31"
        specific.append(d)
        specific_years.add(year_str)  # suppress year-only "YYYY-01-01"

    # "before YYYY" / "prior to YYYY" → treat as end of (YYYY-1)
    for m in _BEFORE_YEAR_PATTERN.finditer(text):
        year_str = m.group(1) or m.group(2)
        prev_year = int(year_str) - 1
        d = f"{prev_year}-12-31"
        specific.append(d)
        specific_years.add(str(prev_year))  # suppress "(YYYY-1)-01-01"
        specific_years.add(year_str)         # suppress "YYYY-01-01" too

    # Year-only: only add if no specific date for that year was found
    year_only: list[str] = []
    for m in _YEAR_ONLY_PATTERN.finditer(text):
        year_str = m.group(1)
        if year_str not in specific_years:
            year_only.append(f"{year_str}-01-01")

    all_dates = specific + year_only

    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for d in all_dates:
        if d not in seen:
            seen.add(d)
            result.append(d)
    return result


def parse_date(date_str: str) -> Optional[date]:
    """Parse an ISO date string to a date object."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def date_gap_days(d1: str, d2: str) -> Optional[float]:
    """Return absolute day gap between two ISO date strings. None if unparseable."""
    a = parse_date(d1)
    b = parse_date(d2)
    if a is None or b is None:
        return None
    return abs((a - b).days)


# ---------------------------------------------------------------------------
# Numeric extraction
# ---------------------------------------------------------------------------

_THRESHOLD_PATTERN = re.compile(
    r"(?:above|below|over|under|at least|more than|less than|exceed|reach)\s*"
    r"\$?\s*([\d,]+(?:\.\d+)?)\s*(?:(?:billion|million|thousand|percent)\b|[%]|(?:k|m|b)(?![a-zA-Z]))?|"
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:(?:billion|million|thousand|percent)\b|[%]|(?:k|m|b)(?![a-zA-Z]))?",
    re.IGNORECASE,
)

_MULTIPLIERS = {
    "billion": 1e9, "b": 1e9,
    "million": 1e6, "m": 1e6,
    "thousand": 1e3, "k": 1e3,
}


def extract_thresholds(text: str) -> list[float]:
    """Extract numeric thresholds from text."""
    results: list[float] = []
    for m in _THRESHOLD_PATTERN.finditer(text):
        # Pattern has two alternatives: group(1) for keyword-prefixed, group(2) for $-prefixed
        raw_group = m.group(1) or m.group(2)
        if not raw_group:
            continue
        raw = raw_group.replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        # Filter out year-like values (1900–2200 with no decimal)
        if 1900.0 <= value <= 2200.0 and value == int(value):
            continue
        # Check for multiplier suffix — must follow digits (possibly with spaces)
        full = m.group(0).lower()
        for suffix, mult in _MULTIPLIERS.items():
            if re.search(r"(?<=[0-9,])\s*" + re.escape(suffix) + r"(?![a-zA-Z])", full):
                value *= mult
                break
        results.append(value)
    return results


def extract_comparators(text: str) -> list[str]:
    """Extract comparison operators mentioned in text."""
    comparators: list[str] = []
    patterns = [
        (r"\bmore than\b|\bexceed[s]?\b|\babove\b|\bover\b|\bat least\b", ">="),
        (r"\bless than\b|\bbelow\b|\bunder\b|\bat most\b", "<="),
        (r"\bexactly\b|\bequal to\b", "=="),
    ]
    for pat, op in patterns:
        if re.search(pat, text, re.IGNORECASE):
            comparators.append(op)
    return list(dict.fromkeys(comparators))  # deduplicate


# ---------------------------------------------------------------------------
# Token overlap
# ---------------------------------------------------------------------------

def token_overlap(text_a: str, text_b: str) -> float:
    """Jaccard similarity of word tokens."""
    tokens_a = set(re.findall(r"\b\w+\b", text_a.lower()))
    tokens_b = set(re.findall(r"\b\w+\b", text_b.lower()))
    if not tokens_a and not tokens_b:
        return 1.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)
