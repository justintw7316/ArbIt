"""Tests for VectorStore persistence (save/load)."""

import os
import tempfile

import numpy as np
import pytest

from vector_db.models import VectorRecord
from vector_db.persistence import load_store, save_store
from vector_db.store import VectorStore


def _rec(id: str, vec: list, ns: str = "default", text: str = "", meta: dict = None) -> VectorRecord:
    return VectorRecord(id=id, vector=vec, text=text, metadata=meta or {}, namespace=ns)


class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        store = VectorStore()
        store.upsert("ns1", [
            _rec("a", [1.0, 0.0, 0.0], ns="ns1", text="hello", meta={"x": 1}),
            _rec("b", [0.0, 1.0, 0.0], ns="ns1", text="world"),
        ])
        store.upsert("ns2", [
            _rec("c", [0.0, 0.0, 1.0], ns="ns2", text="other"),
        ])

        base = str(tmp_path / "test_store")
        count = save_store(store, base)
        assert count == 3

        store2 = VectorStore()
        loaded = load_store(store2, base)
        assert loaded == 3

        assert store2.count("ns1") == 2
        assert store2.count("ns2") == 1

        rec = store2.get("ns1", "a")
        assert rec is not None
        assert rec.text == "hello"
        assert rec.metadata == {"x": 1}
        assert rec.vector == pytest.approx([1.0, 0.0, 0.0], abs=1e-5)

    def test_files_created(self, tmp_path):
        store = VectorStore()
        store.upsert("ns1", [_rec("a", [1.0, 0.0], ns="ns1")])
        base = str(tmp_path / "store")
        save_store(store, base)
        assert os.path.exists(base + ".npy")
        assert os.path.exists(base + ".json")

    def test_save_empty_store(self, tmp_path):
        store = VectorStore()
        base = str(tmp_path / "empty")
        count = save_store(store, base)
        assert count == 0
        store2 = VectorStore()
        loaded = load_store(store2, base)
        assert loaded == 0

    def test_load_missing_npy_raises(self, tmp_path):
        store = VectorStore()
        with pytest.raises(FileNotFoundError):
            load_store(store, str(tmp_path / "nonexistent"))

    def test_load_is_additive(self, tmp_path):
        """Loading into a pre-populated store should add records, not replace."""
        store = VectorStore()
        store.upsert("ns1", [_rec("a", [1.0, 0.0], ns="ns1")])
        base = str(tmp_path / "store")
        save_store(store, base)

        store2 = VectorStore()
        store2.upsert("ns1", [_rec("existing", [0.0, 1.0], ns="ns1")])
        load_store(store2, base)
        assert store2.count("ns1") == 2

    def test_namespace_preserved(self, tmp_path):
        store = VectorStore()
        store.upsert("polymarket", [_rec("pm1", [1.0, 0.0], ns="polymarket")])
        store.upsert("kalshi", [_rec("kl1", [0.0, 1.0], ns="kalshi")])
        base = str(tmp_path / "store")
        save_store(store, base)

        store2 = VectorStore()
        load_store(store2, base)
        assert store2.count("polymarket") == 1
        assert store2.count("kalshi") == 1
        assert store2.get("polymarket", "pm1") is not None
        assert store2.get("kalshi", "kl1") is not None
