"""High-level Collection API — embed + store + query in one call."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .embedder import HashEmbedder, TransformerEmbedder, get_embedder
from .models import QueryResult, VectorRecord
from .similarity import cosine_similarity
from .store import VectorStore
from .utils import generate_id


class Collection:
    """A named collection of text documents with vector similarity search.

    Usage:
        col = Collection("my_signals")
        col.add(["text one", "text two"])
        results = col.query("similar text", top_k=5)
    """

    def __init__(
        self,
        name: str,
        embedder: Optional[object] = None,
        store: Optional[VectorStore] = None,
    ) -> None:
        self.name = name
        self._embedder = embedder or get_embedder()
        self._store = store or VectorStore()

    @property
    def embedder(self):
        return self._embedder

    @property
    def store(self) -> VectorStore:
        return self._store

    def add(
        self,
        texts: List[str],
        ids: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Embed texts and store them. Returns list of record IDs."""
        if ids and len(ids) != len(texts):
            raise ValueError("ids length must match texts length")
        if metadatas and len(metadatas) != len(texts):
            raise ValueError("metadatas length must match texts length")

        record_ids = ids or [generate_id() for _ in texts]
        vectors = self._embedder.embed_batch(texts)

        records = []
        for i, (rid, vec, text) in enumerate(zip(record_ids, vectors, texts)):
            meta = metadatas[i] if metadatas else {}
            records.append(
                VectorRecord(id=rid, vector=vec, text=text, metadata=meta, namespace=self.name)
            )

        self._store.upsert(self.name, records)
        return record_ids

    def add_vectors(
        self,
        vectors: List[List[float]],
        ids: List[str],
        texts: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Store pre-computed vectors (skip embedding)."""
        if len(vectors) != len(ids):
            raise ValueError("vectors and ids must have same length")

        records = []
        for i, (rid, vec) in enumerate(zip(ids, vectors)):
            text = texts[i] if texts else ""
            meta = metadatas[i] if metadatas else {}
            records.append(
                VectorRecord(id=rid, vector=vec, text=text, metadata=meta, namespace=self.name)
            )

        self._store.upsert(self.name, records)
        return ids

    def query(
        self,
        text: str,
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[QueryResult]:
        """Embed query text and return the most similar stored records."""
        query_vec = self._embedder.embed(text)
        return self._store.query(
            namespace=self.name,
            vector=query_vec,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

    def similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between two texts."""
        vec_a = self._embedder.embed(text_a)
        vec_b = self._embedder.embed(text_b)
        return cosine_similarity(vec_a, vec_b)

    def count(self) -> int:
        """Number of records in this collection."""
        return self._store.count(self.name)

    def get(self, id: str) -> Optional[VectorRecord]:
        """Fetch a record by ID."""
        return self._store.get(self.name, id)

    def delete(self, ids: List[str]) -> int:
        """Delete records by ID. Returns count deleted."""
        return self._store.delete(self.name, ids)

    def clear(self) -> None:
        """Remove all records from this collection."""
        self._store.clear(self.name)
