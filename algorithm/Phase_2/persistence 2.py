"""Persistence utilities: save and load a VectorStore to/from disk.

Format:
  {path}.npy   — float32 numpy array of all vectors, shape (N, dim)
  {path}.json  — list of record metadata (id, text, namespace, metadata dict)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .models import VectorRecord

if TYPE_CHECKING:
    from .store import VectorStore


def save_store(store: "VectorStore", path: str) -> int:
    """Persist all records in *store* to disk.

    Creates ``{path}.npy`` (vectors) and ``{path}.json`` (metadata).
    Parent directories are created automatically.

    Args:
        store: VectorStore instance to save.
        path: Base path without extension.

    Returns:
        Number of records saved.
    """
    base = Path(path)
    base.parent.mkdir(parents=True, exist_ok=True)

    records_meta = []
    vectors = []

    with store._lock:
        for ns_records in store._records.values():
            for rec in ns_records.values():
                records_meta.append(
                    {
                        "id": rec.id,
                        "text": rec.text,
                        "namespace": rec.namespace,
                        "metadata": rec.metadata,
                    }
                )
                vectors.append(rec.vector)

    if not vectors:
        np.save(str(base) + ".npy", np.empty((0,), dtype=np.float32))
    else:
        np.save(str(base) + ".npy", np.array(vectors, dtype=np.float32))

    with open(str(base) + ".json", "w", encoding="utf-8") as f:
        json.dump(records_meta, f, ensure_ascii=False)

    return len(records_meta)


def load_store(store: "VectorStore", path: str) -> int:
    """Load records from disk into *store* (additive — does not clear first).

    Args:
        store: VectorStore instance to populate.
        path: Base path without extension (same path used with save_store).

    Returns:
        Number of records loaded.

    Raises:
        FileNotFoundError: If either file is missing.
        ValueError: If vector count does not match metadata count.
    """
    base = Path(path)
    npy_path = str(base) + ".npy"
    json_path = str(base) + ".json"

    if not os.path.exists(npy_path):
        raise FileNotFoundError(f"Vector file not found: {npy_path}")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Metadata file not found: {json_path}")

    vectors = np.load(npy_path)
    with open(json_path, "r", encoding="utf-8") as f:
        records_meta = json.load(f)

    if len(vectors) != len(records_meta):
        raise ValueError(
            f"Vector count ({len(vectors)}) does not match "
            f"metadata count ({len(records_meta)})"
        )

    records_by_ns: dict[str, list[VectorRecord]] = {}
    for i, meta in enumerate(records_meta):
        ns = meta["namespace"]
        records_by_ns.setdefault(ns, []).append(
            VectorRecord(
                id=meta["id"],
                vector=vectors[i].tolist(),
                text=meta["text"],
                metadata=meta["metadata"],
                namespace=ns,
            )
        )

    total = 0
    for ns, recs in records_by_ns.items():
        store.upsert(ns, recs)
        total += len(recs)

    return total
