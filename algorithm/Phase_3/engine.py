"""
Phase 3 Engine — Orchestration.

Runs layers 1–7 for each candidate pair. Supports async batch processing
with asyncio.gather for parallel LLM calls.

Short-circuit exits:
  - Hard contradiction → skip reranker + LLM → REJECT

Dead letter handling:
  - Any unhandled exception → REVIEW verdict with error metadata

Usage (smoke test):
    poetry run python -m algorithm.Phase_3.engine
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from algorithm.Phase_2.models import CandidatePair as Phase2CandidatePair
from algorithm.Phase_3.adapters import ensure_canonical_candidate
from algorithm.models import CandidatePair
from algorithm.Phase_3.arb_filter import check_arb_compatibility
from algorithm.Phase_3.classifier import classify_pair
from algorithm.Phase_3.config import get_config
from algorithm.Phase_3.contradictions import check_contradictions
from algorithm.Phase_3.extractor import extract_features
from algorithm.Phase_3.graph_builder import EventGraph
from algorithm.Phase_3.llm_judge import LLMJudge
from algorithm.Phase_3.mapping import determine_outcome_mapping
from algorithm.Phase_3.models import (
    ArbCompatibilityResult,
    ArbStructureType,
    ContradictionResult,
    LLMJudgment,
    OutcomeMappingResult,
    OutcomeMappingType,
    Phase3Decision,
    RelationshipType,
    Verdict,
)
from algorithm.Phase_3.reranker import build_reranker

logger = logging.getLogger(__name__)


def _calibrate_confidence(
    reranker_score: float,
    llm_confidence: float,
    contradiction: ContradictionResult,
) -> float:
    """
    Weighted blend of signals into a final confidence score.
    - Reranker: 30%
    - LLM confidence: 60%
    - Contradiction absence bonus: 10%
    """
    contradiction_bonus = 0.0 if contradiction.hard_reject else 0.1
    raw = 0.3 * reranker_score + 0.6 * llm_confidence + contradiction_bonus
    return max(0.0, min(1.0, raw))


class Phase3Engine:
    def __init__(self) -> None:
        self._config = get_config()
        self._reranker = build_reranker(
            reranker_type=self._config.reranker_type,
            api_key=self._config.openai_api_key,
        )
        self._llm_judge = LLMJudge(config=self._config)
        self._graph = EventGraph()

    async def process_candidate(
        self, candidate: CandidatePair | Phase2CandidatePair
    ) -> Phase3Decision:
        """
        Run all 7 layers for a single candidate pair.
        Returns a Phase3Decision with full provenance.
        """
        candidate = ensure_canonical_candidate(candidate)
        start_ms = time.monotonic() * 1000
        candidate_id = candidate.candidate_id
        market_a = candidate.market_a
        market_b = candidate.market_b

        logger.info("Phase3: processing candidate %s", candidate_id)

        try:
            # ------------------------------------------------------------------
            # Layer 1: Template classification
            # ------------------------------------------------------------------
            template_a, template_b = classify_pair(market_a, market_b)
            logger.debug(
                "L1 templates: %s=%s, %s=%s",
                market_a.market_id, template_a.primary_template,
                market_b.market_id, template_b.primary_template,
            )

            # ------------------------------------------------------------------
            # Layer 2: Feature extraction
            # ------------------------------------------------------------------
            features_a = extract_features(market_a)
            features_b = extract_features(market_b)
            logger.debug(
                "L2 entities: A=%s, B=%s",
                features_a.primary_entity, features_b.primary_entity,
            )

            # ------------------------------------------------------------------
            # Layer 3: Hard contradiction check
            # ------------------------------------------------------------------
            contradiction = check_contradictions(
                features_a, features_b, template_a, template_b
            )
            if contradiction.flags:
                logger.debug("L3 flags: %s", contradiction.flags)

            if contradiction.hard_reject:
                elapsed = time.monotonic() * 1000 - start_ms
                logger.info(
                    "Phase3: candidate %s REJECTED by contradiction (%.1f ms)",
                    candidate_id, elapsed,
                )
                return Phase3Decision(
                    candidate_id=candidate_id,
                    verdict=Verdict.REJECT,
                    reason=f"Hard contradiction: {'; '.join(contradiction.flags)}",
                    contradiction_flags=contradiction.flags,
                    extracted_features_a=features_a,
                    extracted_features_b=features_b,
                    template_labels=[template_a, template_b],
                    confidence=0.0,
                    processing_time_ms=elapsed,
                )

            # ------------------------------------------------------------------
            # Layer 4: Reranker
            # ------------------------------------------------------------------
            reranker_result = self._reranker.score(market_a, market_b)
            logger.debug("L4 reranker score: %.3f", reranker_result.score)

            # ------------------------------------------------------------------
            # Layer 5: LLM adjudication
            # ------------------------------------------------------------------
            llm_judgment = await self._llm_judge.judge(
                market_a=market_a,
                market_b=market_b,
                template_a=template_a,
                template_b=template_b,
                features_a=features_a,
                features_b=features_b,
                contradiction=contradiction,
                reranker=reranker_result,
            )
            logger.debug(
                "L5 LLM verdict: %s (conf %.2f)", llm_judgment.verdict, llm_judgment.confidence
            )

            # ------------------------------------------------------------------
            # Layer 6a: Outcome mapping
            # ------------------------------------------------------------------
            outcome_mapping = determine_outcome_mapping(market_a, market_b, llm_judgment)

            # ------------------------------------------------------------------
            # Layer 6b: Arb compatibility
            # ------------------------------------------------------------------
            arb_compat = check_arb_compatibility(
                market_a, market_b, llm_judgment, outcome_mapping
            )

            # ------------------------------------------------------------------
            # Final verdict + confidence
            # ------------------------------------------------------------------
            verdict = llm_judgment.verdict
            if not arb_compat.is_compatible and verdict == Verdict.ACCEPT:
                verdict = Verdict.REJECT

            confidence = _calibrate_confidence(
                reranker_result.score, llm_judgment.confidence, contradiction
            )
            if verdict == Verdict.REJECT:
                confidence = 0.0

            elapsed = time.monotonic() * 1000 - start_ms

            decision = Phase3Decision(
                candidate_id=candidate_id,
                verdict=verdict,
                reason=llm_judgment.reasoning,
                contradiction_flags=contradiction.flags,
                extracted_features_a=features_a,
                extracted_features_b=features_b,
                template_labels=[template_a, template_b],
                reranker_score=reranker_result.score,
                llm_verdict=llm_judgment,
                relationship_type=llm_judgment.relationship_type,
                outcome_mapping=outcome_mapping,
                arb_compatibility=arb_compat,
                confidence=confidence,
                processing_time_ms=elapsed,
            )

            # ------------------------------------------------------------------
            # Layer 7: Graph update
            # ------------------------------------------------------------------
            if verdict == Verdict.ACCEPT:
                # Build edge key as "market_id_a:market_id_b"
                keyed = Phase3Decision(
                    **decision.model_dump()
                    | {"candidate_id": f"{market_a.market_id}:{market_b.market_id}"}
                )
                self._graph.add_accepted_pair(keyed)

            logger.info(
                "Phase3: candidate %s → %s (conf %.2f, %.1f ms)",
                candidate_id, verdict, confidence, elapsed,
            )
            return decision

        except Exception as exc:
            elapsed = time.monotonic() * 1000 - start_ms
            logger.exception("Phase3: unexpected error on candidate %s", candidate_id)
            return Phase3Decision(
                candidate_id=candidate_id,
                verdict=Verdict.REVIEW,
                reason="Unexpected error — placed in dead letter queue",
                error=str(exc),
                processing_time_ms=elapsed,
            )

    async def process_batch(
        self, candidates: list[CandidatePair | Phase2CandidatePair]
    ) -> list[Phase3Decision]:
        """Process a batch of candidates in parallel (asyncio.gather)."""
        logger.info("Phase3: processing batch of %d candidates", len(candidates))
        results = await asyncio.gather(
            *[self.process_candidate(c) for c in candidates]
        )
        return list(results)

    def get_event_clusters(self) -> list[set[str]]:
        return self._graph.get_event_clusters()

    def get_arb_baskets(self) -> list[dict[str, object]]:
        return self._graph.get_arb_baskets()


# ---------------------------------------------------------------------------
# Smoke test (poetry run python -m algorithm.Phase_3.engine)
# ---------------------------------------------------------------------------

async def _smoke_test() -> None:
    from datetime import datetime
    from algorithm.models import Market, CandidatePair

    logging.basicConfig(level=logging.DEBUG)

    market_a = Market(
        platform="polymarket",
        market_id="poly_btc_100k",
        question="Will Bitcoin reach $100,000 by end of 2025?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.45, "No": 0.55},
        close_time=datetime(2025, 12, 31),
        fetched_at=datetime.utcnow(),
    )
    market_b = Market(
        platform="kalshi",
        market_id="kalshi_btc_100k",
        question="Bitcoin above $100,000 before January 1, 2026?",
        outcomes=["Yes", "No"],
        prices={"Yes": 0.47, "No": 0.53},
        close_time=datetime(2025, 12, 31),
        fetched_at=datetime.utcnow(),
    )
    pair = CandidatePair(
        candidate_id="test_pair_001",
        market_a=market_a,
        market_b=market_b,
        embedding_similarity=0.91,
    )

    engine = Phase3Engine()
    decision = await engine.process_candidate(pair)
    print("\n=== Phase 3 Decision ===")
    print(decision.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_smoke_test())
