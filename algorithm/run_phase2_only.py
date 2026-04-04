#!/usr/bin/env python3
"""Phase 2 only: load all pre-embedded market vectors, find candidate pairs, save to DB.

Does NOT run Phase 3 (LLM / no-LLM verification), 4 (scoring), or 5 (validation).
Run this to populate candidate_pairs with correct pairings before price history is added.

Usage:
    poetry run python -m algorithm.run_phase2_only
    poetry run python -m algorithm.run_phase2_only --threshold 0.70 --limit 2000
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.70
DEFAULT_LIMIT = 2000   # per platform — covers full pre-embedded pool
DEFAULT_MODEL = "all-mpnet-base-v2"


def run(threshold: float, limit: int, model: str, platforms: list[str]) -> None:
    t_start = time.perf_counter()

    from algorithm.db import get_db, get_db_name, get_mongo_uri
    from algorithm.run_full_pipeline import (
        _load_questions_from_markets,
        _save_candidates_to_db,
    )
    from algorithm.Phase_2.pipeline import ArbitragePipeline
    from algorithm.Phase_2.embedder import TransformerEmbedder

    mongo_uri = get_mongo_uri()
    db = get_db()
    db_name = get_db_name()
    log.info(
        "Connected to %s / %s",
        mongo_uri.split("@")[-1] if "@" in mongo_uri else mongo_uri,
        db_name,
    )

    # ── Load pre-embedded questions (per platform) ────────────────────────────
    with_vectors, without_vectors = _load_questions_from_markets(
        db, platforms, limit, keyword=None
    )

    if without_vectors:
        log.info(
            "Embedding %d new questions with %s ...",
            len(without_vectors),
            model,
        )
        embedder = TransformerEmbedder(model_name=model)
        vectors = embedder.embed_batch([q.text for q in without_vectors])
        for q, vec in zip(without_vectors, vectors):
            q.vector = vec
        # Save new vectors back to DB
        col = db["markets"]
        for q in without_vectors:
            if q.vector is not None:
                col.update_one(
                    {"market_id": q.id},
                    {"$set": {"vector": q.vector,
                              "vector_embedded_at": datetime.now(timezone.utc)}},
                )
        log.info("Saved %d new vectors to markets collection", len(without_vectors))

    all_questions = with_vectors + without_vectors
    markets_present = {q.market for q in all_questions}

    log.info(
        "Total questions: %d across platforms: %s",
        len(all_questions),
        sorted(markets_present),
    )

    if len(markets_present) < 2:
        log.error(
            "Need at least 2 platforms — only found: %s. "
            "Check that both platforms have pre-embedded vectors.",
            markets_present,
        )
        return

    # Per-platform counts
    for plat in sorted(markets_present):
        n = sum(1 for q in all_questions if q.market == plat)
        log.info("  %s: %d questions", plat, n)

    # ── Phase 2: find candidate pairs ────────────────────────────────────────
    pipeline = ArbitragePipeline(
        embedder=TransformerEmbedder(model_name=model),
        similarity_threshold=threshold,
    )
    candidates = pipeline.run(all_questions)

    elapsed = time.perf_counter() - t_start
    log.info(
        "Phase 2 complete: %d candidate pairs at threshold %.2f  (%.2fs)",
        len(candidates),
        threshold,
        elapsed,
    )

    if not candidates:
        log.warning(
            "No pairs found. Try lowering --threshold or increasing --limit. "
            "Current: threshold=%.2f, limit=%d per platform.",
            threshold,
            limit,
        )
        return

    # Score distribution
    scores = [p.similarity_score for p in candidates]
    log.info(
        "Score range: %.4f – %.4f  |  ≥0.80: %d  |  ≥0.85: %d  |  ≥0.90: %d",
        min(scores),
        max(scores),
        sum(1 for s in scores if s >= 0.80),
        sum(1 for s in scores if s >= 0.85),
        sum(1 for s in scores if s >= 0.90),
    )

    # Sample the top 5 pairs for sanity-check
    log.info("Top 5 pairs:")
    for p in candidates[:5]:
        log.info(
            "  [%.3f]  %s  |  A_close=%s  B_close=%s",
            p.similarity_score,
            p.question_a.text[:60],
            p.question_a.metadata.get("close_time", "?")[:10]
            if p.question_a.metadata.get("close_time") else "?",
            p.question_b.metadata.get("close_time", "?")[:10]
            if p.question_b.metadata.get("close_time") else "?",
        )
        log.info(
            "           %s",
            p.question_b.text[:60],
        )

    # ── Upsert candidate pairs into MongoDB ──────────────────────────────────
    saved = _save_candidates_to_db(db, candidates)
    log.info("Saved %d candidate pairs to MongoDB", saved)

    total = time.perf_counter() - t_start
    print(f"\n{'─'*60}")
    print(f"  Phase 2 Summary")
    print(f"{'─'*60}")
    print(f"  Questions loaded       : {len(all_questions)}")
    print(f"  Platforms              : {', '.join(sorted(markets_present))}")
    print(f"  Candidate pairs        : {len(candidates)}  (≥{threshold:.0%} similarity)")
    print(f"    ≥ 90% similarity     : {sum(1 for s in scores if s >= 0.90)}")
    print(f"    ≥ 85% similarity     : {sum(1 for s in scores if s >= 0.85)}")
    print(f"    ≥ 80% similarity     : {sum(1 for s in scores if s >= 0.80)}")
    print(f"  Saved to DB            : {saved}")
    print(f"  Total time             : {total:.2f}s")
    print(f"{'─'*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 2 only: embed + find candidate pairs"
    )
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD,
        help=f"Minimum cosine similarity (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"Max questions to load per platform (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Sentence-transformer model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--platform", nargs="+", default=["kalshi", "polymarket"],
        help="Platforms to include (default: kalshi polymarket)",
    )
    args = parser.parse_args()
    run(
        threshold=args.threshold,
        limit=args.limit,
        model=args.model,
        platforms=args.platform,
    )


if __name__ == "__main__":
    main()
