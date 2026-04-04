"""Tests for embedders."""

import pytest

from vector_db.embedder import HashEmbedder, TransformerEmbedder


class TestHashEmbedder:
    def test_dimensions(self):
        e = HashEmbedder(dimensions=64)
        vec = e.embed("hello world")
        assert len(vec) == 64

    def test_default_dimensions(self):
        e = HashEmbedder()
        vec = e.embed("test")
        assert len(vec) == 128

    def test_deterministic(self):
        e = HashEmbedder()
        v1 = e.embed("same text")
        v2 = e.embed("same text")
        assert v1 == v2

    def test_different_texts_differ(self):
        e = HashEmbedder()
        v1 = e.embed("bitcoin price rising")
        v2 = e.embed("weather forecast sunny")
        assert v1 != v2

    def test_empty_text(self):
        e = HashEmbedder()
        vec = e.embed("")
        assert all(v == 0.0 for v in vec)

    def test_normalized(self):
        e = HashEmbedder()
        vec = e.embed("normalize this vector")
        norm = sum(v * v for v in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_batch(self):
        e = HashEmbedder()
        vecs = e.embed_batch(["hello", "world", "test"])
        assert len(vecs) == 3
        assert all(len(v) == 128 for v in vecs)

    def test_model_name(self):
        e = HashEmbedder(dimensions=96)
        assert e.model_name == "hash-96d"


class TestTransformerEmbedder:
    def test_fallback_on_missing_model(self):
        e = TransformerEmbedder(model_name="nonexistent-model-xyz", allow_download=False)
        vec = e.embed("test text")
        assert len(vec) == 768  # fallback dim matches new default (all-mpnet-base-v2)
        assert "fallback" in e.model_name

    def test_fallback_batch(self):
        e = TransformerEmbedder(model_name="nonexistent-model-xyz", allow_download=False)
        vecs = e.embed_batch(["a", "b"])
        assert len(vecs) == 2

    @pytest.mark.slow
    def test_real_model(self):
        """Integration test — requires model download."""
        e = TransformerEmbedder()
        vec = e.embed("BTC ETH spread arbitrage")
        assert len(vec) == 384
        norm = sum(v * v for v in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-4
