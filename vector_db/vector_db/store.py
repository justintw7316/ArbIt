"""In-memory vector store with namespace partitioning."""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

from .models import QueryResult, VectorRecord
from .similarity import METRICS, cosine_similarity


class VectorStore:
    """Namespace-partitioned, thread-safe in-memory vector database."""

    def __init__(self) -> None:
        self._records: Dict[str, Dict[str, VectorRecord]] = {}
        self._lock = threading.Lock()

    def upsert(self, namespace: str, records: List[VectorRecord]) -> None:
        """Insert or update records in a namespace.

        Raises:
            ValueError: If vector dimensions are inconsistent within the batch
                        or with existing records in the namespace.
        """
        if not records:
            return

        # Validate dimension consistency within the incoming batch
        expected_dim = len(records[0].vector)
        for rec in records:
            if len(rec.vector) != expected_dim:
                raise ValueError(
                    f"Dimension mismatch in batch: expected {expected_dim}, "
                    f"got {len(rec.vector)} for record {rec.id!r}"
                )

        with self._lock:
            if namespace not in self._records:
                self._records[namespace] = {}
            ns = self._records[namespace]

            # Validate against existing records in this namespace
            if ns:
                existing_dim = len(next(iter(ns.values())).vector)
                if expected_dim != existing_dim:
                    raise ValueError(
                        f"Dimension mismatch with existing records in namespace {namespace!r}: "
                        f"existing={existing_dim}, incoming={expected_dim}"
                    )

            for rec in records:
                ns[rec.id] = rec

    def query(
        self,
        namespace: str,
        vector: List[float],
        top_k: int = 10,
        metric: str = "cosine",
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[QueryResult]:
        """Find the most similar records to a query vector.

        Args:
            namespace: Namespace to search.
            vector: Query vector.
            top_k: Number of results to return.
            metric: Similarity metric ("cosine" or "dot").
            metadata_filter: Optional AND-logic metadata filter.

        Returns:
            Ranked list of QueryResult.
        """
        with self._lock:
            ns = dict(self._records.get(namespace, {}))

        if not ns:
            return []

        score_fn: Callable = METRICS.get(metric, cosine_similarity)

        scored = []
        for rec in ns.values():
            if metadata_filter and not _metadata_matches(rec.metadata, metadata_filter):
                continue
            score = score_fn(vector, rec.vector)
            scored.append((rec, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for rank, (rec, score) in enumerate(scored[:top_k], start=1):
            results.append(QueryResult(record=rec, score=score, rank=rank))
        return results

    def delete(self, namespace: str, ids: List[str]) -> int:
        """Delete records by ID. Returns count of deleted records."""
        with self._lock:
            ns = self._records.get(namespace, {})
            deleted = 0
            for rid in ids:
                if rid in ns:
                    del ns[rid]
                    deleted += 1
        return deleted

    def get(self, namespace: str, id: str) -> Optional[VectorRecord]:
        """Fetch a single record by ID."""
        with self._lock:
            return self._records.get(namespace, {}).get(id)

    def list_namespaces(self) -> List[str]:
        """List all namespaces."""
        with self._lock:
            return list(self._records.keys())

    def count(self, namespace: str) -> int:
        """Count records in a namespace."""
        with self._lock:
            return len(self._records.get(namespace, {}))

    def clear(self, namespace: Optional[str] = None) -> None:
        """Clear a namespace, or all namespaces if None."""
        with self._lock:
            if namespace:
                self._records.pop(namespace, None)
            else:
                self._records.clear()


def _metadata_matches(metadata: Dict[str, Any], filt: Dict[str, Any]) -> bool:
    """Check if metadata satisfies all filter conditions (AND logic)."""
    for key, expected in filt.items():
        actual = metadata.get(key)
        if isinstance(expected, list):
            if isinstance(actual, list):
                if not any(e in actual for e in expected):
                    return False
            else:
                if actual not in expected:
                    return False
        else:
            if isinstance(actual, list):
                if expected not in actual:
                    return False
            else:
                if actual != expected:
                    return False
    return True
