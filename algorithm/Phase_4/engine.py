"""Phase 4 — Arbitrage Engine.

Takes matched pairs from Phase 3 and produces scored ArbitrageSignal
objects.  For each pair the engine:

    1. Computes the raw spread and direction.
    2. Builds a feature vector from historical spread data.
    3. Runs the regression model to estimate P(convergence).
    4. Sizes the position with Kelly criterion.
    5. Computes expected value and confidence score.

The output is a ranked list of ArbitrageSignal objects ready for Phase 5.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np

from algorithm.Phase_4.config import MIN_SPREAD, LOOKBACK_DAYS
from algorithm.Phase_4.models import ArbitrageSignal, MatchedPair
from algorithm.Phase_4.spread import compute_spread, two_sided_spread
from algorithm.Phase_4.regression import SpreadConvergenceModel, extract_features
from algorithm.Phase_4.kelly import kelly_size, expected_value

logger = logging.getLogger(__name__)


class ArbitrageEngine:
    """Core Phase 4 processor: scores matched pairs into ArbitrageSignals."""

    def __init__(
        self,
        bankroll: float = 10_000.0,
        model: SpreadConvergenceModel | None = None,
    ) -> None:
        self.bankroll = bankroll
        self.model = model or SpreadConvergenceModel()

    def score_pair(self, pair: MatchedPair) -> ArbitrageSignal | None:
        """Evaluate a single matched pair and return a signal (or None)."""

        # 1. Spread
        raw_spread, direction = compute_spread(pair)
        guaranteed_spread = two_sided_spread(pair)

        if raw_spread < MIN_SPREAD:
            logger.debug("Pair %s: spread %.4f below threshold", pair.pair_id, raw_spread)
            return None

        # 2. Historical spread features
        spread_series, timestamps = self._get_spread_history(pair)
        features = extract_features(
            spread_series=spread_series,
            timestamps=timestamps,
            volume_a=pair.market_a.volume_24h,
            volume_b=pair.market_b.volume_24h,
            close_date=pair.market_a.close_date or pair.market_b.close_date,
        )

        # 3. Regression + economic tightening
        base_prob = self.model.predict_convergence_prob(features)
        match_quality = self._match_quality(pair, guaranteed_spread, raw_spread)

        convergence_prob = round(
            max(0.01, min(0.99, base_prob * (0.55 + 0.45 * match_quality))),
            6,
        )

        favorable_capture = self._estimate_capture_amount(
            raw_spread=raw_spread,
            guaranteed_spread=guaranteed_spread,
            convergence_prob=convergence_prob,
            similarity=pair.similarity_score,
            features=features,
        )
        adverse_move = self._estimate_adverse_move(
            raw_spread=raw_spread,
            similarity=pair.similarity_score,
            features=features,
        )

        if favorable_capture <= 0:
            logger.debug("Pair %s: non-positive capture estimate", pair.pair_id)
            return None

        # 4. Kelly sizing
        kelly_f, position_usd = kelly_size(
            convergence_prob=convergence_prob,
            spread=raw_spread,
            bankroll=self.bankroll,
            reward_per_dollar=favorable_capture,
            risk_per_dollar=adverse_move,
            match_quality=match_quality,
        )

        if position_usd <= 0:
            logger.debug("Pair %s: Kelly says no position", pair.pair_id)
            return None

        # 5. Expected value & confidence
        ev = expected_value(
            convergence_prob,
            raw_spread,
            position_usd,
            reward_per_dollar=favorable_capture,
            risk_per_dollar=adverse_move,
        )
        confidence = self._compute_confidence(
            convergence_prob=convergence_prob,
            raw_spread=raw_spread,
            guaranteed_spread=guaranteed_spread,
            similarity=pair.similarity_score,
            data_points=len(spread_series),
        )

        if ev <= 0 or confidence < 0.35:
            logger.debug(
                "Pair %s: filtered | EV=%.4f conf=%.3f", pair.pair_id, ev, confidence
            )
            return None

        signal = ArbitrageSignal(
            pair_id=pair.pair_id,
            market_a_id=pair.market_a.market_id,
            market_b_id=pair.market_b.market_id,
            platform_a=pair.market_a.platform,
            platform_b=pair.market_b.platform,
            price_a=pair.market_a.yes_price,
            price_b=pair.market_b.yes_price,
            raw_spread=raw_spread,
            direction=direction,
            regression_convergence_prob=convergence_prob,
            expected_profit=ev,
            kelly_fraction=kelly_f,
            recommended_size_usd=position_usd,
            confidence=confidence,
        )

        logger.info(
            "Signal: %s | spread=%.4f conv=%.2f kelly=%.4f size=$%.0f EV=$%.2f conf=%.2f",
            pair.pair_id,
            raw_spread,
            convergence_prob,
            kelly_f,
            position_usd,
            ev,
            confidence,
        )
        return signal

    def score_pairs(self, pairs: list[MatchedPair]) -> list[ArbitrageSignal]:
        """Score all pairs, filter, and rank by expected value."""
        signals = []
        for pair in pairs:
            sig = self.score_pair(pair)
            if sig is not None:
                signals.append(sig)

        signals.sort(key=lambda s: s.expected_profit, reverse=True)
        logger.info("Phase 4 complete: %d signals from %d pairs", len(signals), len(pairs))
        return signals

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_spread_history(
        self, pair: MatchedPair
    ) -> tuple[np.ndarray, list[datetime]]:
        """Pull aligned price histories from MongoDB and compute spread series.

        Falls back to a single-point snapshot if no history is available.
        """
        try:
            from algorithm.db import get_db, PRICE_HISTORY_COL

            db = get_db()
            col = db[PRICE_HISTORY_COL]
            cutoff = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)

            hist_a = list(
                col.find({
                    "platform": pair.market_a.platform.value,
                    "market_id": pair.market_a.market_id,
                    "timestamp": {"$gte": cutoff},
                }).sort("timestamp", 1)
            )
            hist_b = list(
                col.find({
                    "platform": pair.market_b.platform.value,
                    "market_id": pair.market_b.market_id,
                    "timestamp": {"$gte": cutoff},
                }).sort("timestamp", 1)
            )

            if hist_a and hist_b:
                return _align_and_spread(hist_a, hist_b)
        except Exception as exc:
            logger.debug("Could not load spread history from DB: %s", exc)

        # Fallback: single-point from current prices
        current_spread = pair.market_a.yes_price - pair.market_b.yes_price
        return np.array([current_spread]), [datetime.utcnow()]

    @staticmethod
    def _match_quality(
        pair: MatchedPair, guaranteed_spread: float, raw_spread: float
    ) -> float:
        """Blend semantic similarity with structural arbitrage quality."""
        similarity = float(max(0.0, min(1.0, pair.similarity_score)))
        if raw_spread <= 0:
            structural = 0.0
        else:
            structural = min(max(guaranteed_spread / raw_spread, 0.0), 1.0)
        quality = 0.75 * similarity + 0.25 * structural
        return round(max(0.0, min(1.0, quality)), 6)

    @staticmethod
    def _estimate_capture_amount(
        raw_spread: float,
        guaranteed_spread: float,
        convergence_prob: float,
        similarity: float,
        features: "SpreadFeatures",  # noqa: F821
    ) -> float:
        """Estimate how much of the displayed spread is realistically capturable."""
        if raw_spread <= 0:
            return 0.0

        velocity_bonus = 0.15 if features.spread_velocity < 0 else 0.0
        volatility_penalty = (
            min(features.spread_volatility / max(abs(raw_spread), 1e-6), 2.0) * 0.08
        )
        time_penalty = 0.10 if features.time_to_close_days > 180 else 0.0

        capture_ratio = 0.35 + 0.45 * convergence_prob + velocity_bonus
        capture_ratio += 0.10 * min(abs(features.spread_z_score) / 2.5, 1.0)
        capture_ratio -= volatility_penalty + time_penalty
        capture_ratio *= 0.60 + 0.40 * max(0.0, min(1.0, similarity))
        capture_ratio = max(0.05, min(0.95, capture_ratio))

        estimated = raw_spread * capture_ratio
        if guaranteed_spread > 0:
            estimated = max(estimated, guaranteed_spread * 0.90)

        return round(min(estimated, raw_spread), 6)

    @staticmethod
    def _estimate_adverse_move(
        raw_spread: float,
        similarity: float,
        features: "SpreadFeatures",  # noqa: F821
    ) -> float:
        """Estimate downside if the spread fails to converge."""
        if raw_spread <= 0:
            return 0.0

        base = raw_spread * 0.50
        if features.spread_velocity > 0:
            base += min(abs(features.spread_velocity), raw_spread) * 0.75
        if features.time_to_close_days > 90:
            base += raw_spread * 0.15
        if features.spread_volatility > abs(raw_spread):
            base += raw_spread * 0.15

        weak_match_penalty = (1.0 - max(0.0, min(1.0, similarity))) * raw_spread * 0.75
        risk = base + weak_match_penalty
        # For a two-sided binary hedge, the true worst-case loss when markets diverge
        # is (1 - spread), not 1.5 * spread. Cap at the real binary loss floor.
        binary_worst_case = max(1.0 - raw_spread, raw_spread * 0.25)
        return round(min(risk, binary_worst_case), 6)

    @staticmethod
    def _compute_confidence(
        convergence_prob: float,
        raw_spread: float,
        guaranteed_spread: float,
        similarity: float,
        data_points: int,
    ) -> float:
        """Composite confidence score ∈ [0, 1].

        Factors: model confidence, guaranteed spread size, text similarity,
        and amount of historical data.
        """
        w_model = 0.35
        w_spread = 0.25
        w_similarity = 0.25
        w_data = 0.15

        model_score = convergence_prob
        spread_score = (
            min(guaranteed_spread / 0.10, 1.0)
            if guaranteed_spread > 0
            else min(raw_spread / 0.12, 0.7)
        )
        sim_score = similarity
        data_score = min(data_points / 100, 1.0)

        conf = (
            w_model * model_score
            + w_spread * spread_score
            + w_similarity * sim_score
            + w_data * data_score
        )
        return round(max(0.0, min(1.0, conf)), 4)


def persist_signals(signals: list[ArbitrageSignal]) -> int:
    """Write signals to MongoDB."""
    if not signals:
        return 0
    from algorithm.db import get_db, SIGNALS_COL

    db = get_db()
    col = db[SIGNALS_COL]
    for s in signals:
        col.update_one(
            {"pair_id": s.pair_id},
            {"$set": s.model_dump(mode="json")},
            upsert=True,
        )
    return len(signals)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _align_and_spread(
    hist_a: list[dict],
    hist_b: list[dict],
) -> tuple[np.ndarray, list[datetime]]:
    """Align two price histories to hourly buckets and compute spread."""

    def _bucket(ts: datetime) -> datetime:
        return ts.replace(minute=0, second=0, microsecond=0)

    buckets_a: dict[datetime, float] = {}
    buckets_b: dict[datetime, float] = {}

    for doc in hist_a:
        ts = doc["timestamp"]
        if not isinstance(ts, datetime):
            ts = datetime.fromisoformat(str(ts))
        buckets_a[_bucket(ts)] = float(doc["yes_price"])

    for doc in hist_b:
        ts = doc["timestamp"]
        if not isinstance(ts, datetime):
            ts = datetime.fromisoformat(str(ts))
        buckets_b[_bucket(ts)] = float(doc["yes_price"])

    common = sorted(set(buckets_a.keys()) & set(buckets_b.keys()))
    if not common:
        last_a = float(hist_a[-1]["yes_price"])
        last_b = float(hist_b[-1]["yes_price"])
        return np.array([last_a - last_b]), [datetime.utcnow()]

    spreads = np.array([buckets_a[t] - buckets_b[t] for t in common])
    return spreads, common
