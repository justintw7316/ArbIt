"""vector_db — lightweight vector database with transformer embeddings."""

from .candidate_finder import CandidateFinder
from .collection import Collection
from .mongo_adapter import MongoAdapter
from .embedder import HashEmbedder, TransformerEmbedder, get_embedder
from .models import CandidatePair, MarketQuestion, QueryResult, VectorRecord
from .persistence import load_store, save_store
from .pipeline import ArbitragePipeline
from .similarity import cosine_similarity, dot_product, euclidean_distance, l2_normalize
from .store import VectorStore
from .utils import chunk_text, generate_id, preprocess

__all__ = [
    # Core storage
    "Collection",
    "VectorStore",
    "VectorRecord",
    "QueryResult",
    # Embedders
    "HashEmbedder",
    "TransformerEmbedder",
    "get_embedder",
    # Arbitrage pipeline (step 2 → step 3 interface)
    "ArbitragePipeline",
    "CandidateFinder",
    "MarketQuestion",
    "CandidatePair",
    # MongoDB integration
    "MongoAdapter",
    # Persistence
    "save_store",
    "load_store",
    # Similarity utilities
    "cosine_similarity",
    "dot_product",
    "euclidean_distance",
    "l2_normalize",
    # Text utilities
    "chunk_text",
    "generate_id",
    "preprocess",
]
