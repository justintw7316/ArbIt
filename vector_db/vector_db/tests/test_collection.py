"""End-to-end tests for the Collection API."""

import pytest

from vector_db import Collection
from vector_db.embedder import HashEmbedder


@pytest.fixture
def col():
    """Collection with deterministic hash embedder for fast tests."""
    return Collection("test", embedder=HashEmbedder(dimensions=64))


class TestCollection:
    def test_add_and_count(self, col):
        col.add(["hello world", "foo bar"])
        assert col.count() == 2

    def test_add_with_ids(self, col):
        ids = col.add(["text one", "text two"], ids=["id1", "id2"])
        assert ids == ["id1", "id2"]
        assert col.get("id1") is not None

    def test_add_auto_ids(self, col):
        ids = col.add(["text one", "text two"])
        assert len(ids) == 2
        assert ids[0] != ids[1]

    def test_add_with_metadata(self, col):
        col.add(
            texts=["btc signal"],
            ids=["s1"],
            metadatas=[{"asset": "BTC", "exchange": "binance"}],
        )
        rec = col.get("s1")
        assert rec.metadata["asset"] == "BTC"

    def test_query_returns_ranked_results(self, col):
        col.add(
            texts=[
                "bitcoin price rising sharply",
                "ethereum gas fees increasing",
                "weather forecast sunny tomorrow",
            ],
            ids=["btc", "eth", "weather"],
        )
        results = col.query("bitcoin price movement", top_k=2)
        assert len(results) == 2
        assert results[0].rank == 1
        assert results[0].score >= results[1].score

    def test_query_with_metadata_filter(self, col):
        col.add(
            texts=["signal a", "signal b", "signal c"],
            ids=["a", "b", "c"],
            metadatas=[
                {"type": "crypto"},
                {"type": "equity"},
                {"type": "crypto"},
            ],
        )
        results = col.query("signal", metadata_filter={"type": "crypto"})
        assert all(r.record.metadata["type"] == "crypto" for r in results)

    def test_similarity(self, col):
        score = col.similarity("bitcoin price", "bitcoin price")
        assert score == 1.0

    def test_similarity_different_texts(self, col):
        score = col.similarity("bitcoin price", "weather forecast")
        assert 0.0 <= score < 1.0

    def test_delete(self, col):
        col.add(["a", "b", "c"], ids=["1", "2", "3"])
        deleted = col.delete(["1", "2"])
        assert deleted == 2
        assert col.count() == 1

    def test_clear(self, col):
        col.add(["a", "b"])
        col.clear()
        assert col.count() == 0

    def test_add_vectors_directly(self, col):
        col.add_vectors(
            vectors=[[1.0, 0.0], [0.0, 1.0]],
            ids=["v1", "v2"],
            texts=["vec one", "vec two"],
        )
        assert col.count() == 2
        assert col.get("v1").text == "vec one"

    def test_mismatched_ids_raises(self, col):
        with pytest.raises(ValueError):
            col.add(["a", "b"], ids=["only_one"])

    def test_mismatched_metadata_raises(self, col):
        with pytest.raises(ValueError):
            col.add(["a", "b"], metadatas=[{"x": 1}])

    @pytest.mark.slow
    def test_transformer_semantic_similarity(self):
        """Integration test with real transformer — verifies semantic quality."""
        col = Collection("semantic_test")
        col.add(
            texts=[
                "BTC-ETH spread widening on Binance vs Coinbase",
                "ETH gas fees spiking, DEX arbitrage windows opening",
                "Treasury yield curve inversion deepening",
                "Solana validator downtime creating price dislocations",
            ],
            ids=["s1", "s2", "s3", "s4"],
        )
        results = col.query("Bitcoin Ethereum price spread divergence", top_k=2)
        # The BTC-ETH spread signal should rank highest
        assert results[0].record.id == "s1"
