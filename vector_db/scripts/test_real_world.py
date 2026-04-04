#!/usr/bin/env python3
"""Real-world integration test for the ArbitragePipeline.

Run this script directly to evaluate similarity quality on realistic
prediction market data. Adjust SIMILARITY_THRESHOLD and MODEL_NAME to
iterate toward the best candidate set for step 3.

Usage:
    cd vector_db
    python scripts/test_real_world.py
    python scripts/test_real_world.py --threshold 0.80 --model all-mpnet-base-v2
    python scripts/test_real_world.py --hash   # fast offline run (no model download)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from vector_db import ArbitragePipeline, CandidatePair, MarketQuestion
from vector_db.embedder import HashEmbedder, TransformerEmbedder

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Sample data — structured exactly like step 1 scraper output.
# These mirror real Polymarket / Kalshi questions as of early 2025.
# Extend / replace with live API data once step 1 is integrated.
# ---------------------------------------------------------------------------

POLYMARKET_QUESTIONS: list[MarketQuestion] = [
    MarketQuestion(
        id="pm_001",
        text="Will the Federal Reserve cut interest rates in Q1 2025?",
        market="polymarket",
        price=0.38,
        metadata={"volume": 1_200_000, "close_time": "2025-03-31"},
    ),
    MarketQuestion(
        id="pm_002",
        text="Will Bitcoin (BTC) exceed $150,000 by end of 2025?",
        market="polymarket",
        price=0.41,
        metadata={"volume": 3_500_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="pm_003",
        text="Will Donald Trump be impeached in 2025?",
        market="polymarket",
        price=0.05,
        metadata={"volume": 850_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="pm_004",
        text="Will Ethereum (ETH) reach $10,000 before 2026?",
        market="polymarket",
        price=0.29,
        metadata={"volume": 920_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="pm_005",
        text="Will the US enter a recession in 2025?",
        market="polymarket",
        price=0.33,
        metadata={"volume": 1_100_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="pm_006",
        text="Will SpaceX Starship reach orbit in 2025?",
        market="polymarket",
        price=0.72,
        metadata={"volume": 650_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="pm_007",
        text="Will Taylor Swift win a Grammy in 2025?",
        market="polymarket",
        price=0.60,
        metadata={"volume": 200_000, "close_time": "2025-02-28"},
    ),
    MarketQuestion(
        id="pm_008",
        text="Will the Fed NOT raise rates in 2025?",
        market="polymarket",
        price=0.88,
        metadata={"volume": 500_000, "close_time": "2025-12-31"},
    ),
]

KALSHI_QUESTIONS: list[MarketQuestion] = [
    MarketQuestion(
        id="kl_001",
        text="Federal Reserve rate cut before April 2025?",
        market="kalshi",
        price=0.35,
        metadata={"volume": 800_000, "close_time": "2025-04-01"},
    ),
    MarketQuestion(
        id="kl_002",
        text="Will BTC price surpass $150k USD by December 31, 2025?",
        market="kalshi",
        price=0.44,
        metadata={"volume": 2_100_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="kl_003",
        text="Trump impeachment proceedings in 2025?",
        market="kalshi",
        price=0.04,
        metadata={"volume": 400_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="kl_004",
        text="Will ETH hit $10,000 by end of 2025?",
        market="kalshi",
        price=0.27,
        metadata={"volume": 700_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="kl_005",
        text="US recession by end of 2025?",
        market="kalshi",
        price=0.30,
        metadata={"volume": 900_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="kl_006",
        text="SpaceX Starship successful orbital flight in 2025?",
        market="kalshi",
        price=0.70,
        metadata={"volume": 450_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="kl_007",
        text="Will the Academy Awards go to a film about AI in 2025?",
        market="kalshi",
        price=0.15,
        metadata={"volume": 150_000, "close_time": "2025-03-31"},
    ),
    MarketQuestion(
        id="kl_008",
        text="Will the Fed raise interest rates in 2025?",
        market="kalshi",
        price=0.10,
        metadata={"volume": 600_000, "close_time": "2025-12-31"},
    ),
]

MANIFOLD_QUESTIONS: list[MarketQuestion] = [
    MarketQuestion(
        id="mf_001",
        text="Does Bitcoin top $150,000 during 2025?",
        market="manifold",
        price=0.39,
        metadata={"volume": 50_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="mf_002",
        text="Will there be a US economic recession in calendar year 2025?",
        market="manifold",
        price=0.35,
        metadata={"volume": 30_000, "close_time": "2025-12-31"},
    ),
    MarketQuestion(
        id="mf_003",
        text="Will Elon Musk leave Tesla's CEO role before 2026?",
        market="manifold",
        price=0.22,
        metadata={"volume": 25_000, "close_time": "2025-12-31"},
    ),
]


def print_section(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print("=" * 70)


def print_pair(pair: CandidatePair, index: int) -> None:
    neg_flag = " ⚠ NEGATION" if pair.has_potential_negation else ""
    print(f"\n  [{index}] score={pair.similarity_score:.4f}{neg_flag}")
    print(f"      A [{pair.question_a.market}] p={pair.question_a.price:.2f}  {pair.question_a.text}")
    print(f"      B [{pair.question_b.market}] p={pair.question_b.price:.2f}  {pair.question_b.text}")
    if pair.has_potential_negation:
        print(f"      ↑ Negation tokens: {pair.negation_tokens}")
    arb = abs(pair.question_a.price - pair.question_b.price)
    if arb > 0.02:
        print(f"      ↑ Price spread: {arb:.3f}  ← potential arb signal")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test ArbitragePipeline on sample data")
    parser.add_argument("--threshold", type=float, default=0.75, help="Similarity threshold (default: 0.75)")
    parser.add_argument("--model", type=str, default="all-mpnet-base-v2", help="Transformer model name")
    parser.add_argument("--hash", action="store_true", help="Use HashEmbedder (fast, offline, low quality)")
    args = parser.parse_args()

    print_section("ArbitragePipeline — Real-World Test")
    print(f"  threshold={args.threshold}  hash={args.hash}")
    if not args.hash:
        print(f"  model={args.model}")

    embedder = HashEmbedder(dimensions=128) if args.hash else TransformerEmbedder(model_name=args.model)
    pipeline = ArbitragePipeline(
        embedder=embedder,
        similarity_threshold=args.threshold,
    )

    all_questions = POLYMARKET_QUESTIONS + KALSHI_QUESTIONS + MANIFOLD_QUESTIONS

    print_section("Step 1: Embedding & search")
    t0 = time.perf_counter()
    candidates = pipeline.run(all_questions)
    elapsed = time.perf_counter() - t0
    print(f"  {len(all_questions)} questions → {len(candidates)} candidate pairs in {elapsed:.2f}s")

    print_section("All candidate pairs (sorted by similarity)")
    if not candidates:
        print("  No candidates found. Try lowering --threshold.")
    for i, pair in enumerate(candidates, start=1):
        print_pair(pair, i)

    # --- Summary stats
    print_section("Summary")
    negation_pairs = [p for p in candidates if p.has_potential_negation]
    high_conf = [p for p in candidates if p.similarity_score >= 0.90]
    price_arb = [p for p in candidates if abs(p.question_a.price - p.question_b.price) > 0.05]
    print(f"  Total candidates:      {len(candidates)}")
    print(f"  High confidence (≥0.9): {len(high_conf)}")
    print(f"  Negation flagged:       {len(negation_pairs)}")
    print(f"  Price spread > 5%:      {len(price_arb)}  ← primary arb targets for step 3+")

    # --- Show negation examples explicitly
    if negation_pairs:
        print_section("Negation-flagged pairs (require extra care in step 3)")
        for p in negation_pairs:
            print(f"  • [{p.question_a.market}] {p.question_a.text}")
            print(f"    [{p.question_b.market}] {p.question_b.text}")
            print(f"    tokens: {p.negation_tokens}  score: {p.similarity_score:.4f}\n")


if __name__ == "__main__":
    main()
