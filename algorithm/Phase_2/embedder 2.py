"""Transformer and hash-based text embedders."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import List, Optional, Protocol

log = logging.getLogger(__name__)


class Embedder(Protocol):
    """Protocol for all embedders."""

    @property
    def dimensions(self) -> int: ...

    @property
    def model_name(self) -> str: ...

    def embed(self, text: str) -> List[float]: ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]: ...


class HashEmbedder:
    """Deterministic SHA256-based embedder for testing and offline use."""

    def __init__(self, dimensions: int = 128) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return f"hash-{self._dimensions}d"

    def embed(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self._dimensions

        vec = [0.0] * self._dimensions
        tokens = re.findall(r"[a-zA-Z0-9_#+.\-]+", text.lower())
        for tok in tokens:
            h = hashlib.sha256(tok.encode()).hexdigest()
            idx = int(h[:8], 16) % self._dimensions
            sign = 1.0 if int(h[8:10], 16) % 2 == 0 else -1.0
            weight = 1.0 + len(tok) / 20.0
            vec[idx] += sign * weight

        # L2 normalize
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


class TransformerEmbedder:
    """Sentence-transformer embedder with lazy model loading and hash fallback."""

    def __init__(
        self,
        model_name: str = "all-mpnet-base-v2",
        fallback_dim: int = 768,
        allow_download: bool = True,
    ) -> None:
        self._model_name = model_name
        self._fallback_dim = fallback_dim
        self._allow_download = allow_download
        self._model = None
        self._fallback: Optional[HashEmbedder] = None
        self._loaded = False

    def _load_model(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self._model_name,
                local_files_only=not self._allow_download,
            )
            log.info("Loaded model: %s", self._model_name)
        except Exception as e:
            log.warning("Failed to load %s, falling back to HashEmbedder: %s", self._model_name, e)
            self._fallback = HashEmbedder(dimensions=self._fallback_dim)

    @property
    def dimensions(self) -> int:
        if self._fallback:
            return self._fallback.dimensions
        return self._fallback_dim

    @property
    def model_name(self) -> str:
        if self._fallback:
            return f"{self._model_name}(fallback:hash)"
        return self._model_name

    def embed(self, text: str) -> List[float]:
        self._load_model()
        if self._fallback:
            return self._fallback.embed(text)
        if not text or not text.strip():
            return [0.0] * self.dimensions
        try:
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        except Exception as e:
            log.warning("Encode failed, activating fallback: %s", e)
            self._fallback = HashEmbedder(dimensions=self._fallback_dim)
            return self._fallback.embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self._load_model()
        if self._fallback:
            return self._fallback.embed_batch(texts)
        if not texts:
            return []
        try:
            vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return [v.tolist() for v in vecs]
        except Exception as e:
            log.warning("Batch encode failed, activating fallback: %s", e)
            self._fallback = HashEmbedder(dimensions=self._fallback_dim)
            return self._fallback.embed_batch(texts)


def get_embedder(
    model_name: Optional[str] = None,
    use_hash_fallback: bool = False,
) -> Embedder:
    """Factory function to create an embedder.

    Args:
        model_name: Transformer model name (default: all-mpnet-base-v2).
            Recommended models for prediction market similarity:
            - "all-mpnet-base-v2" (768-dim) — best general-purpose quality
            - "multi-qa-mpnet-base-dot-v1" (768-dim) — optimised for Q&A matching
            - "all-MiniLM-L6-v2" (384-dim) — faster, lower quality
        use_hash_fallback: If True, return HashEmbedder directly (for tests/offline).
    """
    if use_hash_fallback:
        return HashEmbedder()
    return TransformerEmbedder(model_name=model_name or "all-mpnet-base-v2")
