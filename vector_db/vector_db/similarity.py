"""Similarity and distance functions for vector comparison."""

from __future__ import annotations

import math
from typing import List


def l2_normalize(vec: List[float]) -> List[float]:
    """Normalize a vector to unit length (L2 norm)."""
    if not vec:
        return []
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return [0.0] * len(vec)
    return [x / norm for x in vec]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors.

    Assumes vectors are L2-normalized (dot product == cosine similarity).
    If not normalized, normalizes them first.
    Returns value clamped to [0.0, 1.0].
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    sim = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, sim))


def dot_product(a: List[float], b: List[float]) -> float:
    """Raw dot product between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def euclidean_distance(a: List[float], b: List[float]) -> float:
    """Euclidean (L2) distance between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# Metric registry for store.py
METRICS = {
    "cosine": cosine_similarity,
    "dot": dot_product,
}
