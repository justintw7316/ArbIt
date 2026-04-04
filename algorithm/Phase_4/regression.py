"""Regression model for predicting spread convergence in Phase 4.

Given a historical time-series of spreads between two matched markets,
we train a logistic regression model to predict whether the current spread
will converge (shrink toward zero) within a lookahead window.

Features:
    1. current_spread        — the spread right now
    2. mean_spread           — rolling mean of recent spreads
    3. spread_velocity       — rate of change (first derivative)
    4. spread_volatility     — rolling std-dev
    5. volume_ratio          — relative activity on the two platforms
    6. time_to_close_days    — days until market resolution
    7. spread_z_score        — how unusual the current spread is
    8. max_spread_lookback   — max spread in the lookback window
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from algorithm.Phase_4.config import LOOKBACK_DAYS

logger = logging.getLogger(__name__)

# Optional scikit-learn import — falls back to heuristic if unavailable
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available; SpreadConvergenceModel will use heuristic only")


@dataclass
class SpreadFeatures:
    current_spread: float
    mean_spread: float
    spread_velocity: float
    spread_volatility: float
    volume_ratio: float
    time_to_close_days: float
    spread_z_score: float
    max_spread_lookback: float

    def to_array(self) -> np.ndarray:
        return np.array([
            self.current_spread,
            self.mean_spread,
            self.spread_velocity,
            self.spread_volatility,
            self.volume_ratio,
            self.time_to_close_days,
            self.spread_z_score,
            self.max_spread_lookback,
        ]).reshape(1, -1)


def extract_features(
    spread_series: np.ndarray,
    timestamps: "np.ndarray | list[datetime]",
    volume_a: float,
    volume_b: float,
    close_date: datetime | None,
    lookback: int = LOOKBACK_DAYS,
) -> SpreadFeatures:
    """Build the feature vector from raw spread history."""
    if len(spread_series) < 3:
        return SpreadFeatures(
            current_spread=float(spread_series[-1]) if len(spread_series) else 0.0,
            mean_spread=float(np.mean(spread_series)) if len(spread_series) else 0.0,
            spread_velocity=0.0,
            spread_volatility=0.01,
            volume_ratio=1.0,
            time_to_close_days=365.0,
            spread_z_score=0.0,
            max_spread_lookback=float(np.max(np.abs(spread_series))) if len(spread_series) else 0.0,
        )

    current = float(spread_series[-1])
    mean = float(np.mean(spread_series))
    std = float(np.std(spread_series)) or 0.01

    recent = spread_series[-min(5, len(spread_series)):]
    velocity = float(np.mean(np.diff(recent))) if len(recent) > 1 else 0.0

    vr = (volume_a / volume_b) if volume_b > 0 else 10.0
    vr = min(vr, 10.0)

    if close_date and isinstance(timestamps[-1] if hasattr(timestamps, '__getitem__') else None, datetime):
        ttc = (close_date - datetime.utcnow()).total_seconds() / 86400
        ttc = max(ttc, 0.0)
    else:
        ttc = 365.0

    z = (current - mean) / std

    return SpreadFeatures(
        current_spread=current,
        mean_spread=mean,
        spread_velocity=velocity,
        spread_volatility=std,
        volume_ratio=round(vr, 4),
        time_to_close_days=round(ttc, 2),
        spread_z_score=round(z, 4),
        max_spread_lookback=float(np.max(np.abs(spread_series))),
    )


class SpreadConvergenceModel:
    """Logistic regression predicting P(spread converges within window).

    Falls back to a rule-based heuristic when scikit-learn is unavailable
    or when the model has not been trained yet.
    """

    def __init__(self) -> None:
        self._is_fitted = False
        if _SKLEARN_AVAILABLE:
            self.model = LogisticRegression(max_iter=1000, C=1.0)
            self.scaler = StandardScaler()
        else:
            self.model = None
            self.scaler = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train on historical (feature, label) pairs."""
        if not _SKLEARN_AVAILABLE:
            logger.warning("scikit-learn unavailable — cannot train model")
            return
        if len(X) < 10:
            logger.warning("Too few samples to train regression — using heuristic")
            return
        X_scaled = self.scaler.fit_transform(X)  # type: ignore[union-attr]
        self.model.fit(X_scaled, y)  # type: ignore[union-attr]
        self._is_fitted = True
        acc = self.model.score(X_scaled, y)  # type: ignore[union-attr]
        logger.info(f"Convergence model fitted on {len(X)} samples, train accuracy = {acc:.3f}")

    def predict_convergence_prob(self, features: SpreadFeatures) -> float:
        """Return P(spread converges) ∈ [0, 1]."""
        if self._is_fitted and _SKLEARN_AVAILABLE:
            X = self.scaler.transform(features.to_array())  # type: ignore[union-attr]
            return float(self.model.predict_proba(X)[0, 1])  # type: ignore[union-attr]
        return self._heuristic(features)

    @staticmethod
    def _heuristic(f: SpreadFeatures) -> float:
        """Rule-based fallback when no trained model is available."""
        score = 0.5

        if f.current_spread > 0.10:
            score += 0.15
        elif f.current_spread > 0.05:
            score += 0.08

        if abs(f.spread_z_score) > 2.0:
            score += 0.12
        elif abs(f.spread_z_score) > 1.0:
            score += 0.06

        if f.spread_velocity < -0.005:
            score += 0.10
        elif f.spread_velocity > 0.005:
            score -= 0.08

        if f.time_to_close_days < 7:
            score += 0.05
        elif f.time_to_close_days > 180:
            score -= 0.05

        if 0.3 <= f.volume_ratio <= 3.0:
            score += 0.05

        return round(max(0.01, min(0.99, score)), 4)


def label_convergence(
    spread_series: np.ndarray,
    lookahead: int = 24,
    threshold_pct: float = 0.50,
) -> np.ndarray:
    """Generate binary convergence labels from a spread history array.

    label[t] = 1 if spread[t + lookahead] ≤ (1 − threshold_pct) × spread[t].
    """
    n = len(spread_series) - lookahead
    labels = np.zeros(n, dtype=int)
    for i in range(n):
        current = abs(spread_series[i])
        future = abs(spread_series[i + lookahead])
        if current > 0 and future <= current * (1 - threshold_pct):
            labels[i] = 1
    return labels
