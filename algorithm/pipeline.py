"""Full ArbIt pipeline: Phase 2 → Phase 3 → Phase 4 → Phase 5.

This module wires together all four phases into a single end-to-end function.

    Phase 2: embed market questions → candidate pairs
    Phase 3: validate candidate pairs → accept/reject decisions
    Phase 4: score accepted pairs → arbitrage signals
    Phase 5: validate signals against live market conditions → executable opportunities

Usage::

    from algorithm.pipeline import run_pipeline
    from algorithm.Phase_2.models import MarketQuestion

    questions = [...]  # list of MarketQuestion from Phase 1 / test data
    results = await run_pipeline(questions)
    for opp in results.executable_opportunities:
        print(opp)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Sequence

from algorithm.Phase_2.models import CandidatePair as Phase2CandidatePair
from algorithm.Phase_2.models import MarketQuestion
from algorithm.Phase_2.pipeline import ArbitragePipeline
from algorithm.Phase_3.engine import Phase3Engine
from algorithm.Phase_3.models import Phase3Decision, Verdict
from algorithm.Phase_4.adapters import filter_accepted
from algorithm.Phase_4.engine import ArbitrageEngine, persist_signals
from algorithm.Phase_4.models import ArbitrageSignal, MatchedPair
from algorithm.Phase_5.models import ValidatedOpportunity
from algorithm.Phase_5.validator import TradeValidator, persist_validated

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Full output of one pipeline run."""

    # Phase 2 output
    candidate_pairs: list[Phase2CandidatePair] = field(default_factory=list)

    # Phase 3 output
    phase3_decisions: list[Phase3Decision] = field(default_factory=list)
    accepted_pairs: list[Phase3Decision] = field(default_factory=list)

    # Phase 4 output
    matched_pairs: list[MatchedPair] = field(default_factory=list)
    arbitrage_signals: list[ArbitrageSignal] = field(default_factory=list)

    # Phase 5 output
    validated_opportunities: list[ValidatedOpportunity] = field(default_factory=list)
    executable_opportunities: list[ValidatedOpportunity] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"Pipeline result: "
            f"{len(self.candidate_pairs)} candidates → "
            f"{len(self.accepted_pairs)} accepted → "
            f"{len(self.arbitrage_signals)} signals → "
            f"{len(self.executable_opportunities)} executable"
        )


async def run_pipeline(
    questions: Sequence[MarketQuestion],
    *,
    phase2_threshold: float = 0.70,
    bankroll: float = 10_000.0,
    persist: bool = False,
) -> PipelineResult:
    """Run the full Phase 2 → 3 → 4 → 5 pipeline.

    Parameters
    ----------
    questions        : market questions from Phase 1 (or test data)
    phase2_threshold : cosine similarity threshold for Phase 2
    bankroll         : total capital for Kelly sizing in Phase 4
    persist          : whether to write signals and opportunities to MongoDB
    """
    result = PipelineResult()

    # ── Phase 2: Embeddings & candidate search ────────────────────────────────
    logger.info("Phase 2: embedding %d questions", len(questions))
    phase2 = ArbitragePipeline(similarity_threshold=phase2_threshold)
    result.candidate_pairs = phase2.run(list(questions))
    logger.info("Phase 2: %d candidate pairs found", len(result.candidate_pairs))

    if not result.candidate_pairs:
        return result

    # ── Phase 3: Validation ───────────────────────────────────────────────────
    logger.info("Phase 3: validating %d pairs", len(result.candidate_pairs))
    phase3 = Phase3Engine()

    # Phase 3 accepts either Phase2CandidatePair or canonical CandidatePair
    result.phase3_decisions = await asyncio.gather(
        *[phase3.process_candidate(p) for p in result.candidate_pairs]
    )
    result.accepted_pairs = [
        d for d in result.phase3_decisions if d.verdict == Verdict.ACCEPT
    ]
    logger.info(
        "Phase 3: %d/%d accepted",
        len(result.accepted_pairs),
        len(result.phase3_decisions),
    )

    # Pair decisions with their original candidates (same list, same order)
    accepted_candidates: list[Phase2CandidatePair] = [
        cand
        for cand, dec in zip(result.candidate_pairs, result.phase3_decisions)
        if dec.verdict == Verdict.ACCEPT
    ]

    if not accepted_candidates:
        return result

    # ── Phase 3 → Phase 4 adapter ─────────────────────────────────────────────
    # Convert Phase2CandidatePair → canonical CandidatePair using the existing
    # Phase 3 adapter, then filter to only ACCEPT'd pairs for Phase 4.
    from algorithm.Phase_3.adapters import phase2_candidate_to_canonical

    canonical_candidates = [
        phase2_candidate_to_canonical(c) for c in accepted_candidates
    ]
    result.matched_pairs = filter_accepted(canonical_candidates, result.accepted_pairs)

    if not result.matched_pairs:
        return result

    # ── Phase 4: Arbitrage Engine ─────────────────────────────────────────────
    logger.info("Phase 4: scoring %d matched pairs", len(result.matched_pairs))
    phase4 = ArbitrageEngine(bankroll=bankroll)
    result.arbitrage_signals = phase4.score_pairs(result.matched_pairs)
    logger.info("Phase 4: %d signals produced", len(result.arbitrage_signals))

    if persist and result.arbitrage_signals:
        n = persist_signals(result.arbitrage_signals)
        logger.info("Phase 4: persisted %d signals", n)

    if not result.arbitrage_signals:
        return result

    # ── Phase 5: Live Validation ──────────────────────────────────────────────
    logger.info("Phase 5: validating %d signals", len(result.arbitrage_signals))
    phase5 = TradeValidator()
    result.validated_opportunities = phase5.validate_batch(result.arbitrage_signals)
    result.executable_opportunities = [
        o for o in result.validated_opportunities if o.executable
    ]

    if persist and result.validated_opportunities:
        n = persist_validated(result.validated_opportunities)
        logger.info("Phase 5: persisted %d validated opportunities", n)

    logger.info(result.summary)
    return result


