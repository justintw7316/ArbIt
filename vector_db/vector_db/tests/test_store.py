"""Tests for the vector store."""

from vector_db.models import VectorRecord
from vector_db.store import VectorStore


def _rec(id: str, vec: list, meta: dict = None) -> VectorRecord:
    return VectorRecord(id=id, vector=vec, text=f"text_{id}", metadata=meta or {})


class TestVectorStore:
    def test_upsert_and_count(self):
        store = VectorStore()
        store.upsert("ns1", [_rec("a", [1, 0, 0]), _rec("b", [0, 1, 0])])
        assert store.count("ns1") == 2

    def test_upsert_overwrites(self):
        store = VectorStore()
        store.upsert("ns1", [_rec("a", [1, 0, 0])])
        store.upsert("ns1", [_rec("a", [0, 1, 0])])
        assert store.count("ns1") == 1
        assert store.get("ns1", "a").vector == [0, 1, 0]

    def test_query_cosine(self):
        store = VectorStore()
        store.upsert("ns1", [
            _rec("a", [1, 0, 0]),
            _rec("b", [0, 1, 0]),
            _rec("c", [0.9, 0.1, 0]),
        ])
        results = store.query("ns1", [1, 0, 0], top_k=2)
        assert len(results) == 2
        assert results[0].record.id == "a"
        assert results[0].rank == 1
        assert results[0].score > results[1].score

    def test_query_empty_namespace(self):
        store = VectorStore()
        results = store.query("empty", [1, 0, 0])
        assert results == []

    def test_metadata_filter(self):
        store = VectorStore()
        store.upsert("ns1", [
            _rec("a", [1, 0, 0], {"type": "crypto"}),
            _rec("b", [0.9, 0.1, 0], {"type": "equity"}),
            _rec("c", [0.8, 0.2, 0], {"type": "crypto"}),
        ])
        results = store.query("ns1", [1, 0, 0], metadata_filter={"type": "crypto"})
        assert len(results) == 2
        assert all(r.record.metadata["type"] == "crypto" for r in results)

    def test_metadata_filter_list(self):
        store = VectorStore()
        store.upsert("ns1", [
            _rec("a", [1, 0, 0], {"tags": ["btc", "eth"]}),
            _rec("b", [0.9, 0.1, 0], {"tags": ["sol"]}),
        ])
        results = store.query("ns1", [1, 0, 0], metadata_filter={"tags": ["btc"]})
        assert len(results) == 1
        assert results[0].record.id == "a"

    def test_delete(self):
        store = VectorStore()
        store.upsert("ns1", [_rec("a", [1, 0, 0]), _rec("b", [0, 1, 0])])
        deleted = store.delete("ns1", ["a"])
        assert deleted == 1
        assert store.count("ns1") == 1
        assert store.get("ns1", "a") is None

    def test_delete_nonexistent(self):
        store = VectorStore()
        assert store.delete("ns1", ["xyz"]) == 0

    def test_get(self):
        store = VectorStore()
        store.upsert("ns1", [_rec("a", [1, 0, 0])])
        rec = store.get("ns1", "a")
        assert rec is not None
        assert rec.id == "a"

    def test_get_missing(self):
        store = VectorStore()
        assert store.get("ns1", "nope") is None

    def test_list_namespaces(self):
        store = VectorStore()
        store.upsert("alpha", [_rec("a", [1, 0])])
        store.upsert("beta", [_rec("b", [0, 1])])
        ns = store.list_namespaces()
        assert set(ns) == {"alpha", "beta"}

    def test_clear_namespace(self):
        store = VectorStore()
        store.upsert("ns1", [_rec("a", [1, 0])])
        store.upsert("ns2", [_rec("b", [0, 1])])
        store.clear("ns1")
        assert "ns1" not in store.list_namespaces()
        assert store.count("ns2") == 1

    def test_clear_all(self):
        store = VectorStore()
        store.upsert("ns1", [_rec("a", [1, 0])])
        store.upsert("ns2", [_rec("b", [0, 1])])
        store.clear()
        assert store.list_namespaces() == []

    def test_namespace_isolation(self):
        store = VectorStore()
        store.upsert("ns1", [_rec("a", [1, 0, 0])])
        store.upsert("ns2", [_rec("a", [0, 1, 0])])
        r1 = store.get("ns1", "a")
        r2 = store.get("ns2", "a")
        assert r1.vector != r2.vector
