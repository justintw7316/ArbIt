"""Cross-market candidate pair finder for arbitrage detection."""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional, Tuple

import numpy as np

from .embedder import Embedder, TransformerEmbedder
from .models import CandidatePair, MarketQuestion

# Negation tokens that may indicate semantic opposition between two questions.
# A pair is flagged when one question has tokens from this set that the other lacks.
# Step 3 (LLM verification) must confirm whether the pair is truly equivalent or inverted.
_NEGATION_TOKENS = frozenset([
    "not", "no", "never", "won't", "wouldn't", "can't", "cannot",
    "doesn't", "didn't", "isn't", "aren't", "wasn't", "weren't",
    "fail", "fails", "failed", "failing", "without", "neither",
    "nor", "refuse", "refuses", "refused", "against",
    "lose", "loses", "lost",
])


def _detect_negation(text_a: str, text_b: str) -> Tuple[bool, List[str]]:
    """Detect asymmetric negation between two question texts.

    Returns (has_asymmetric_negation, list_of_asymmetric_negation_tokens).
    Asymmetric means one text contains a negation token the other does not.
    """
    tokens_a = set(re.findall(r"\b\w+\b", text_a.lower()))
    tokens_b = set(re.findall(r"\b\w+\b", text_b.lower()))
    neg_a = tokens_a & _NEGATION_TOKENS
    neg_b = tokens_b & _NEGATION_TOKENS
    asymmetric = sorted(neg_a.symmetric_difference(neg_b))
    return bool(asymmetric), asymmetric


class CandidateFinder:
    """Finds cross-market candidate pairs for arbitrage detection.

    Embeds all questions using a single batch call, then computes a full
    pairwise similarity matrix with numpy (O(N*M) but very fast on CPU
    for typical market sizes of < 10k questions per market).

    Pairs above `similarity_threshold` are returned sorted by score descending.
    The `has_potential_negation` flag on each pair signals to step 3 that an
    LLM should verify semantic direction before treating the pair as an arb.

    Usage::

        finder = CandidateFinder(similarity_threshold=0.85)
        pairs = finder.find_candidates(polymarket_questions, kalshi_questions)
        # → List[CandidatePair] sorted by similarity_score desc
    """

    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        similarity_threshold: float = 0.85,
    ) -> None:
        """
        Args:
            embedder: Embedder to use. Defaults to TransformerEmbedder (all-mpnet-base-v2).
            similarity_threshold: Minimum cosine similarity to include a pair [0, 1].
                                  Every pair above this threshold is returned — no cap.
        """
        self._embedder = embedder or TransformerEmbedder()
        self.similarity_threshold = similarity_threshold

    def find_candidates(
        self,
        questions_a: List[MarketQuestion],
        questions_b: List[MarketQuestion],
    ) -> List[CandidatePair]:
        """Find candidate arbitrage pairs between two market question lists.

        Args:
            questions_a: Questions from market A (e.g., polymarket).
            questions_b: Questions from market B (e.g., kalshi).

        Returns:
            List of CandidatePair sorted by similarity_score descending.
        """
        if not questions_a or not questions_b:
            return []

        # Use pre-computed vectors if available (loaded from MongoDB),
        # otherwise embed from text. Avoids re-embedding on every batch run.
        if all(q.vector is not None for q in questions_a):
            vecs_a = np.array([q.vector for q in questions_a], dtype=np.float32)
        else:
            vecs_a = np.array(self._embedder.embed_batch([q.text for q in questions_a]), dtype=np.float32)

        if all(q.vector is not None for q in questions_b):
            vecs_b = np.array([q.vector for q in questions_b], dtype=np.float32)
        else:
            vecs_b = np.array(self._embedder.embed_batch([q.text for q in questions_b]), dtype=np.float32)

        # Full pairwise cosine similarity. Since sentence-transformers normalises
        # to unit length, dot product == cosine similarity.
        # Shape: (len_a, len_b)
        sim_matrix = vecs_a @ vecs_b.T

        # Find ALL pairs above the threshold in one shot — no top-k cap.
        # Using top-k per question would silently miss genuine pairs when a
        # question has more than k matches above the threshold.
        above_threshold = np.argwhere(sim_matrix >= self.similarity_threshold)

        pairs: List[CandidatePair] = []

        for i, j in above_threshold:
            score = float(sim_matrix[i, j])
            q_a = questions_a[i]
            q_b = questions_b[j]

            has_neg, neg_tokens = _detect_negation(q_a.text, q_b.text)
            pair_id = hashlib.sha256(
                f"{q_a.id}|{q_b.id}".encode()
            ).hexdigest()[:16]

            pairs.append(
                CandidatePair(
                    id=pair_id,
                    question_a=q_a,
                    question_b=q_b,
                    similarity_score=score,
                    has_potential_negation=has_neg,
                    negation_tokens=neg_tokens,
                )
            )

        pairs.sort(key=lambda p: p.similarity_score, reverse=True)
        return pairs

    def find_candidates_all_markets(
        self,
        questions_by_market: Dict[str, List[MarketQuestion]],
    ) -> List[CandidatePair]:
        """Find candidates across every unique pair of markets.

        Args:
            questions_by_market: Mapping from market name to its questions.

        Returns:
            Merged, deduplicated list of CandidatePair sorted by score descending.
        """
        markets = list(questions_by_market.keys())
        all_pairs: List[CandidatePair] = []

        for i in range(len(markets)):
            for j in range(i + 1, len(markets)):
                pairs = self.find_candidates(
                    questions_by_market[markets[i]],
                    questions_by_market[markets[j]],
                )
                all_pairs.extend(pairs)

        all_pairs.sort(key=lambda p: p.similarity_score, reverse=True)
        return all_pairs
