"""Tests for similarity functions."""

from algorithm.Phase_2.similarity import (
    cosine_similarity,
    dot_product,
    euclidean_distance,
    l2_normalize,
)


def test_cosine_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert cosine_similarity(v, v) == 1.0


def test_cosine_orthogonal_vectors():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert cosine_similarity(a, b) == 0.0


def test_cosine_similar_vectors():
    a = [1.0, 1.0, 0.0]
    b = [1.0, 0.0, 0.0]
    sim = cosine_similarity(a, b)
    assert 0.5 < sim < 1.0


def test_cosine_empty_vectors():
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], []) == 0.0


def test_cosine_dimension_mismatch():
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0


def test_cosine_zero_vectors():
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_dot_product_basic():
    a = [1.0, 2.0, 3.0]
    b = [4.0, 5.0, 6.0]
    assert dot_product(a, b) == 32.0


def test_dot_product_empty():
    assert dot_product([], []) == 0.0


def test_euclidean_distance_same():
    v = [1.0, 2.0, 3.0]
    assert euclidean_distance(v, v) == 0.0


def test_euclidean_distance_known():
    a = [0.0, 0.0]
    b = [3.0, 4.0]
    assert abs(euclidean_distance(a, b) - 5.0) < 1e-9


def test_l2_normalize():
    v = [3.0, 4.0]
    normed = l2_normalize(v)
    assert abs(normed[0] - 0.6) < 1e-9
    assert abs(normed[1] - 0.8) < 1e-9


def test_l2_normalize_zero():
    v = [0.0, 0.0]
    normed = l2_normalize(v)
    assert normed == [0.0, 0.0]


def test_l2_normalize_empty():
    assert l2_normalize([]) == []
