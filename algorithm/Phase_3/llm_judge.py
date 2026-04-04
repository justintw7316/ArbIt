"""
Layer 5 — LLM Judge.

Uses DeepSeek (via OpenAI-compatible API) to adjudicate whether two markets
are equivalent or dependency-linked. Includes async support, retry logic,
simple token-bucket rate limiter, and a dead-letter path on failure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable, Optional

from openai import AsyncOpenAI

from algorithm.models import Market
from algorithm.Phase_3.config import Phase3Config, get_config
from algorithm.Phase_3.models import (
    ContradictionResult,
    ExtractedFeatures,
    LLMJudgment,
    RelationshipType,
    RerankerResult,
    TemplateResult,
    Verdict,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a prediction market validation expert for an arbitrage system.
Your task is to determine whether two prediction market questions refer to the same underlying
real-world event, or whether one is a derivative of the other.

RULES:
- You must respond with ONLY valid JSON — no markdown, no prose outside the JSON object.
- Be LENIENT: if markets MIGHT be equivalent or complementary, prefer ACCEPT or REVIEW over REJECT.
- Only output REJECT when markets clearly refer to different events with no plausible arbitrage link.
- Hard contradictions (already flagged for you) are strong rejection signals, but you still make the call.

OUTPUT FORMAT (strict JSON):
{
  "verdict": "ACCEPT" | "REJECT" | "REVIEW",
  "relationship_type": "equivalent" | "complement" | "subset" | "superset" | "related_but_not_arb_compatible" | "unrelated",
  "confidence": 0.0–1.0,
  "reasoning": "one paragraph explanation",
  "outcome_hints": {"yes_a": "yes_b", "no_a": "no_b"}
}"""


def _build_user_prompt(
    market_a: Market,
    market_b: Market,
    template_a: Optional[TemplateResult],
    template_b: Optional[TemplateResult],
    features_a: Optional[ExtractedFeatures],
    features_b: Optional[ExtractedFeatures],
    contradiction: Optional[ContradictionResult],
    reranker: Optional[RerankerResult],
) -> str:
    lines: list[str] = ["=== MARKET A ==="]
    lines.append(f"Platform: {market_a.platform}")
    lines.append(f"Question: {market_a.question}")
    if market_a.description:
        lines.append(f"Description: {market_a.description[:300]}")
    lines.append(f"Outcomes: {market_a.outcomes}")
    if market_a.resolution_rules:
        lines.append(f"Resolution: {market_a.resolution_rules[:200]}")
    if template_a:
        lines.append(f"Template: {template_a.primary_template} (conf {template_a.confidence:.2f})")
    if features_a:
        lines.append(f"Primary entity: {features_a.primary_entity}")
        lines.append(f"Dates: {features_a.dates}")
        lines.append(f"Thresholds: {features_a.thresholds}")

    lines.append("\n=== MARKET B ===")
    lines.append(f"Platform: {market_b.platform}")
    lines.append(f"Question: {market_b.question}")
    if market_b.description:
        lines.append(f"Description: {market_b.description[:300]}")
    lines.append(f"Outcomes: {market_b.outcomes}")
    if market_b.resolution_rules:
        lines.append(f"Resolution: {market_b.resolution_rules[:200]}")
    if template_b:
        lines.append(f"Template: {template_b.primary_template} (conf {template_b.confidence:.2f})")
    if features_b:
        lines.append(f"Primary entity: {features_b.primary_entity}")
        lines.append(f"Dates: {features_b.dates}")
        lines.append(f"Thresholds: {features_b.thresholds}")

    lines.append("\n=== SIGNALS ===")
    if contradiction:
        lines.append(f"Contradiction flags: {contradiction.flags}")
        lines.append(f"Hard reject signal: {contradiction.hard_reject}")
    if reranker:
        lines.append(f"Reranker score: {reranker.score:.3f}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Token bucket rate limiter
# ---------------------------------------------------------------------------

class _TokenBucket:
    """Simple token bucket for rate limiting async calls."""

    def __init__(self, rate_per_second: float) -> None:
        self._rate = rate_per_second
        self._tokens = rate_per_second
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


# ---------------------------------------------------------------------------
# LLM Judge
# ---------------------------------------------------------------------------

class LLMJudge:
    def __init__(
        self,
        config: Optional[Phase3Config] = None,
        cache_hook: Optional[Callable[[str, LLMJudgment], None]] = None,
    ) -> None:
        self._config = config or get_config()
        self._cache_hook = cache_hook
        self._rate_limiter = _TokenBucket(self._config.llm_rate_limit_rps)
        self._client = AsyncOpenAI(
            api_key=self._config.deepseek_api_key or "placeholder",
            base_url=self._config.deepseek_base_url,
        )

    async def judge(
        self,
        market_a: Market,
        market_b: Market,
        template_a: Optional[TemplateResult] = None,
        template_b: Optional[TemplateResult] = None,
        features_a: Optional[ExtractedFeatures] = None,
        features_b: Optional[ExtractedFeatures] = None,
        contradiction: Optional[ContradictionResult] = None,
        reranker: Optional[RerankerResult] = None,
    ) -> LLMJudgment:
        """
        Call the LLM to adjudicate the market pair. Retries up to max_retries
        on malformed JSON. Returns a REVIEW verdict on persistent failure.
        """
        user_prompt = _build_user_prompt(
            market_a, market_b, template_a, template_b,
            features_a, features_b, contradiction, reranker,
        )

        last_error: str = ""
        for attempt in range(1, self._config.deepseek_max_retries + 1):
            await self._rate_limiter.acquire()
            try:
                response = await self._client.chat.completions.create(
                    model=self._config.deepseek_model,
                    temperature=self._config.deepseek_temperature,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content or ""
                judgment = self._parse_response(raw)
                if self._cache_hook:
                    cache_key = f"{market_a.market_id}:{market_b.market_id}"
                    self._cache_hook(cache_key, judgment)
                return judgment
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "LLM judge attempt %d/%d failed: %s",
                    attempt, self._config.deepseek_max_retries, last_error,
                )
                if attempt < self._config.deepseek_max_retries:
                    await asyncio.sleep(2 ** attempt)  # exponential back-off

        # Dead letter: return REVIEW verdict with error info
        return LLMJudgment(
            verdict=Verdict.REVIEW,
            relationship_type=RelationshipType.UNRELATED,
            confidence=0.0,
            reasoning=f"LLM call failed after {self._config.deepseek_max_retries} attempts: {last_error}",
            raw_response=last_error,
        )

    def _parse_response(self, raw: str) -> LLMJudgment:
        """Parse and validate the JSON response from the LLM."""
        # Strip potential markdown fences
        text = raw.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            text = text.rstrip("`").strip()

        data = json.loads(text)

        # Coerce verdict
        verdict_str = str(data.get("verdict", "REVIEW")).upper()
        try:
            verdict = Verdict(verdict_str)
        except ValueError:
            verdict = Verdict.REVIEW

        # Coerce relationship_type
        rel_str = str(data.get("relationship_type", "unrelated")).lower()
        try:
            rel = RelationshipType(rel_str)
        except ValueError:
            rel = RelationshipType.UNRELATED

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return LLMJudgment(
            verdict=verdict,
            relationship_type=rel,
            confidence=confidence,
            reasoning=str(data.get("reasoning", "")),
            outcome_hints=dict(data.get("outcome_hints", {})),
            raw_response=raw,
        )
