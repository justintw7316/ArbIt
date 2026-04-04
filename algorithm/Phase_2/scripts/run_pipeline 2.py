#!/usr/bin/env python3
"""Step 2 pipeline runner — connects MongoDB to the ArbitragePipeline.

This is the single entry point that runs after the step 1 scraper deposits
questions into MongoDB. Call it on a schedule or trigger it manually.

What it does:
    1. Load questions from MongoDB that don't have vectors yet
    2. Embed them with the transformer model
    3. Write vectors back onto the question documents
    4. Load ALL questions (now all have vectors)
    5. Run the similarity comparison
    6. Write candidate pairs to MongoDB for steps 3–7 to consume

Usage:
    poetry run python -m algorithm.Phase_2.scripts.run_pipeline
    poetry run python -m algorithm.Phase_2.scripts.run_pipeline --threshold 0.75
    poetry run python -m algorithm.Phase_2.scripts.run_pipeline --mongo mongodb+srv://user:pass@cluster.mongodb.net
    MONGO_URI=mongodb://localhost:27017 poetry run python -m algorithm.Phase_2.scripts.run_pipeline
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from algorithm.Phase_2.embedder import TransformerEmbedder
from algorithm.Phase_2.mongo_adapter import MongoAdapter
from algorithm.Phase_2.pipeline import ArbitragePipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DATABASE = "prediction_markets"
DEFAULT_THRESHOLD = 0.70


def run(mongo_uri: str, database: str, threshold: float, model: str) -> None:
    t_start = time.perf_counter()

    log.info("Connecting to MongoDB at %s / %s", mongo_uri, database)
    adapter = MongoAdapter(mongo_uri, database=database)

    # ----------------------------------------------------------------
    # Step A: embed any questions that don't have vectors yet
    # ----------------------------------------------------------------
    new_questions = adapter.load_questions_without_vectors()

    if new_questions:
        log.info("Embedding %d new questions with %s ...", len(new_questions), model)
        embedder = TransformerEmbedder(model_name=model)
        vectors = embedder.embed_batch([q.text for q in new_questions])

        for q, vec in zip(new_questions, vectors):
            q.vector = vec

        saved = adapter.save_vectors(new_questions)
        log.info("Saved vectors for %d questions", saved)
    else:
        log.info("No new questions to embed")

    # ----------------------------------------------------------------
    # Step B: run similarity comparison across all embedded questions
    # ----------------------------------------------------------------
    all_questions = adapter.load_questions_with_vectors()

    if not all_questions:
        log.warning("No embedded questions in MongoDB — nothing to compare")
        adapter.close()
        return

    market_counts = adapter.count_questions()
    log.info("Market breakdown: %s", market_counts)

    markets = set(q.market for q in all_questions)
    if len(markets) < 2:
        log.warning("Only one market found (%s) — need at least 2 for cross-market pairs", markets)
        adapter.close()
        return

    # All questions already have vectors — CandidateFinder skips re-embedding
    pipeline = ArbitragePipeline(
        embedder=TransformerEmbedder(model_name=model),  # won't be called (vectors present)
        similarity_threshold=threshold,
    )
    candidates = pipeline.run(all_questions)
    log.info("Found %d candidate pairs at threshold %.2f", len(candidates), threshold)

    # ----------------------------------------------------------------
    # Step C: write candidate pairs to MongoDB
    # ----------------------------------------------------------------
    written = adapter.save_candidates(candidates)
    log.info("Wrote %d candidate pairs to MongoDB", written)

    adapter.close()
    elapsed = time.perf_counter() - t_start
    log.info("Pipeline complete in %.2fs", elapsed)

    # Summary for monitoring
    negation_count = sum(1 for p in candidates if p.has_potential_negation)
    high_conf = sum(1 for p in candidates if p.similarity_score >= 0.90)
    print(f"\n{'─'*50}")
    print(f"  Questions processed : {len(all_questions)}")
    print(f"  Candidate pairs     : {len(candidates)}")
    print(f"  High confidence ≥90%: {high_conf}")
    print(f"  Negation flagged    : {negation_count}  ← step 3 must verify")
    print(f"  Time                : {elapsed:.2f}s")
    print(f"{'─'*50}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 2 ArbitragePipeline against MongoDB"
    )
    parser.add_argument(
        "--mongo",
        default=os.environ.get("MONGO_URI", DEFAULT_MONGO_URI),
        help=f"MongoDB connection string (or set MONGO_URI env var). Default: {DEFAULT_MONGO_URI}",
    )
    parser.add_argument(
        "--database",
        default=os.environ.get("MONGO_DATABASE", DEFAULT_DATABASE),
        help=f"MongoDB database name. Default: {DEFAULT_DATABASE}",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.environ.get("SIMILARITY_THRESHOLD", DEFAULT_THRESHOLD)),
        help=f"Similarity threshold for candidate pairs. Default: {DEFAULT_THRESHOLD}",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("EMBEDDING_MODEL", "all-mpnet-base-v2"),
        help="Transformer model name. Default: all-mpnet-base-v2",
    )
    args = parser.parse_args()

    run(
        mongo_uri=args.mongo,
        database=args.database,
        threshold=args.threshold,
        model=args.model,
    )


if __name__ == "__main__":
    main()
