"""End-to-end arbitrage pipeline: market questions → candidate pairs.

This is the main step 2 component. It accepts structured market questions
produced by the step 1 scraper and outputs candidate pairs for step 3
(LLM verification of semantic equivalence / direction).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .candidate_finder import CandidateFinder
from .embedder import Embedder, TransformerEmbedder
from .models import CandidatePair, MarketQuestion

log = logging.getLogger(__name__)


class ArbitragePipeline:
    """End-to-end pipeline from market questions to candidate arbitrage pairs.

    Step 2 in the quant arbitrage system:

        [Step 1 scraper] → List[MarketQuestion]
            → ArbitragePipeline.run()
        → List[CandidatePair]   ← input for [Step 3 LLM verification]

    The pipeline:
    1. Groups questions by market.
    2. Batch-embeds each market's questions with a transformer model.
    3. Computes pairwise cosine similarity across every market combination.
    4. Returns pairs above the similarity threshold, annotated with a
       negation flag for step 3 to handle.

    Usage::

        pipeline = ArbitragePipeline(similarity_threshold=0.85)
        candidates = pipeline.run(all_questions)
        for pair in candidates:
            print(pair)
    """

    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        similarity_threshold: float = 0.85,
    ) -> None:
        """
        Args:
            embedder: Embedder to use. Defaults to TransformerEmbedder (all-mpnet-base-v2).
                      Inject a HashEmbedder for fast offline tests.
            similarity_threshold: Minimum cosine similarity for a pair to be considered
                                  a candidate [0.0, 1.0]. Every pair above this is returned.
                                  Benchmark result: 0.70 gives F1=0.926 across 6 sectors.
        """
        self._embedder = embedder or TransformerEmbedder()
        self._finder = CandidateFinder(
            embedder=self._embedder,
            similarity_threshold=similarity_threshold,
        )

    @property
    def similarity_threshold(self) -> float:
        return self._finder.similarity_threshold

    @similarity_threshold.setter
    def similarity_threshold(self, value: float) -> None:
        self._finder.similarity_threshold = value

    def run(self, questions: List[MarketQuestion]) -> List[CandidatePair]:
        """Run the pipeline on a flat list of market questions.

        Automatically groups by market and finds all cross-market pairs.

        Args:
            questions: All market questions across all markets (mixed).

        Returns:
            Candidate pairs sorted by similarity_score descending.
        """
        if not questions:
            return []

        by_market: Dict[str, List[MarketQuestion]] = {}
        for q in questions:
            by_market.setdefault(q.market, []).append(q)

        markets = list(by_market.keys())
        log.info(
            "ArbitragePipeline: %d questions across %d markets %s",
            len(questions),
            len(markets),
            markets,
        )

        if len(markets) < 2:
            log.warning(
                "Only one market (%s) — no cross-market pairs possible", markets
            )
            return []

        candidates = self._finder.find_candidates_all_markets(by_market)
        log.info("ArbitragePipeline: %d candidate pairs found", len(candidates))
        return candidates

    def run_two_markets(
        self,
        questions_a: List[MarketQuestion],
        questions_b: List[MarketQuestion],
    ) -> List[CandidatePair]:
        """Compare two specific market question lists directly.

        Use this when you already have questions split by market.
        """
        if not questions_a or not questions_b:
            return []
        return self._finder.find_candidates(questions_a, questions_b)
