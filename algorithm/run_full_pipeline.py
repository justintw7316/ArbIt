#!/usr/bin/env python3
"""Full pipeline runner: MongoDB Atlas → Phase 2 → 3 → 4 → 5.

Reads from the `markets` collection (platform/market_id/question/yes_price schema),
runs embedding-based similarity matching, LLM validation, arbitrage scoring, and
live-style validation.

Usage:
    poetry run python -m algorithm.run_full_pipeline
    poetry run python -m algorithm.run_full_pipeline --threshold 0.75 --limit 500
    poetry run python -m algorithm.run_full_pipeline --platform kalshi polymarket
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.70
DEFAULT_MODEL = "all-mpnet-base-v2"
DEFAULT_LIMIT = 500  # cap per platform to keep runtime reasonable


# ── Schema adapter: markets collection → MarketQuestion ──────────────────────

def _markets_doc_to_question(doc: dict):
    """Convert a `markets` collection document to a Phase 2 MarketQuestion."""
    from algorithm.Phase_2.models import MarketQuestion

    metadata = {k: v for k, v in doc.items()
                if k not in ("platform", "market_id", "question", "yes_price",
                              "no_price", "vector", "vector_embedded_at", "_id")}
    # Build prices dict for downstream phases
    yes_p = float(doc.get("yes_price") or 0.5)
    no_p = float(doc.get("no_price") or round(1.0 - yes_p, 6))
    metadata["prices"] = {"Yes": yes_p, "No": no_p}
    metadata["outcomes"] = ["Yes", "No"]
    if doc.get("end_date"):
        metadata["close_time"] = doc["end_date"]
    if doc.get("market_id"):
        metadata["market_id"] = doc["market_id"]

    return MarketQuestion(
        id=str(doc["market_id"]),
        text=str(doc["question"]),
        market=str(doc["platform"]),
        price=yes_p,
        metadata=metadata,
        vector=doc.get("vector"),
    )


def _load_questions_from_markets(db, platforms: list[str], limit: int, keyword: Optional[str] = None):
    """Load MarketQuestion objects from the markets collection.

    Loads up to `limit` questions PER PLATFORM so that every platform is
    represented equally in the candidate matrix.  Without this guarantee a
    single-query approach returns all documents from the first platform in
    insertion order, leaving cross-market similarity matrix with only one side.
    """
    col = db["markets"]
    base_query: dict = {}
    if keyword:
        base_query["question"] = {"$regex": keyword, "$options": "i"}

    active_platforms = platforms or _get_platforms(col)
    with_vectors: list = []
    without_vectors: list = []

    for plat in active_platforms:
        plat_query = {**base_query, "platform": plat}

        # Prefer pre-embedded questions (avoids re-embedding cost)
        plat_with = [
            _markets_doc_to_question(d)
            for d in col.find(
                {**plat_query, "vector": {"$exists": True}},
                {"price_history": 0},
            ).limit(limit)
        ]
        with_vectors.extend(plat_with)

        # Fill remaining slots with un-embedded questions
        remaining = max(0, limit - len(plat_with))
        if remaining > 0:
            docs = list(
                col.find(
                    {**plat_query, "vector": {"$exists": False}},
                    {"price_history": 0},
                ).limit(remaining)
            )
            without_vectors.extend(_markets_doc_to_question(d) for d in docs)

    log.info(
        "Loaded %d questions (%d pre-embedded, %d new) across %d platforms%s",
        len(with_vectors) + len(without_vectors),
        len(with_vectors),
        len(without_vectors),
        len(active_platforms),
        f" [keyword={keyword!r}]" if keyword else "",
    )
    return with_vectors, without_vectors


def _get_platforms(col) -> list[str]:
    return [r["_id"] for r in col.aggregate([{"$group": {"_id": "$platform"}}])]


def _save_vectors_to_markets(db, questions) -> int:
    """Write computed vectors back to the markets collection."""
    col = db["markets"]
    count = 0
    for q in questions:
        if q.vector is None:
            continue
        result = col.update_one(
            {"market_id": q.id},
            {"$set": {"vector": q.vector, "vector_embedded_at": datetime.now(timezone.utc)}},
        )
        count += result.modified_count
    log.info("Saved vectors for %d markets", count)
    return count


def _save_candidates_to_db(db, candidates) -> int:
    """Upsert Phase 2 candidate pairs into candidate_pairs collection."""
    from algorithm.Phase_2.mongo_adapter import _pair_to_doc

    col = db["candidate_pairs"]
    count = 0
    for pair in candidates:
        doc = _pair_to_doc(pair)
        result = col.update_one({"id": pair.id}, {"$set": doc}, upsert=True)
        count += 1 if result.upserted_id is not None else result.modified_count
    log.info("Saved %d candidate pairs to MongoDB", count)
    return count


# ── Phase 3 async wrapper ─────────────────────────────────────────────────────

async def _run_phase3(candidates):
    from algorithm.Phase_3.engine import Phase3Engine
    from algorithm.Phase_3.adapters import phase2_candidate_to_canonical

    canonical = [phase2_candidate_to_canonical(c) for c in candidates]
    engine = Phase3Engine()
    decisions = await engine.process_batch(canonical)
    return canonical, decisions


def _run_phase3_no_llm(candidates, similarity_threshold: float = 0.80):
    """Phase 3 without LLM: uses Phase 2 embedding similarity + entity/template checks.

    Decision logic (in order):
      1. REJECT if templates are structurally incompatible (e.g. range-bucket vs binary-winner)
      2. REJECT if entities clearly differ (entity mismatch flag)
      3. REJECT if market close dates are too far apart (date_gap_exceeded)
      4. ACCEPT if embedding_similarity >= similarity_threshold
      5. REJECT otherwise
    """
    from algorithm.Phase_3.adapters import phase2_candidate_to_canonical
    from algorithm.Phase_3.classifier import classify_pair
    from algorithm.Phase_3.contradictions import check_contradictions
    from algorithm.Phase_3.extractor import extract_features
    from algorithm.Phase_3.models import Phase3Decision, RelationshipType, Verdict

    canonical = [phase2_candidate_to_canonical(c) for c in candidates]
    decisions = []

    # Build a map: canonical candidate_id → phase2 similarity score
    sim_map = {
        phase2_candidate_to_canonical(c).candidate_id: c.similarity_score
        for c in candidates
    }

    for candidate in canonical:
        market_a, market_b = candidate.market_a, candidate.market_b
        embedding_sim = sim_map.get(candidate.candidate_id, candidate.embedding_similarity)

        try:
            template_a, template_b = classify_pair(market_a, market_b)
            features_a = extract_features(market_a)
            features_b = extract_features(market_b)
            contradiction = check_contradictions(features_a, features_b, template_a, template_b)

            structural_reject = any(
                "entity_mismatch" in f or "incompatible_templates" in f or "date_gap_exceeded" in f
                for f in contradiction.flags
            )

            if structural_reject:
                verdict = Verdict.REJECT
                reason = f"Structural contradiction: {'; '.join(f for f in contradiction.flags if 'entity_mismatch' in f or 'incompatible_templates' in f or 'date_gap_exceeded' in f)}"
                confidence = 0.0
            elif embedding_sim >= similarity_threshold:
                verdict = Verdict.ACCEPT
                reason = f"No-LLM: embedding_sim={embedding_sim:.3f} >= {similarity_threshold}"
                confidence = round(embedding_sim, 4)
            else:
                verdict = Verdict.REJECT
                reason = f"No-LLM: embedding_sim={embedding_sim:.3f} < {similarity_threshold}"
                confidence = 0.0

            decisions.append(Phase3Decision(
                candidate_id=candidate.candidate_id,
                verdict=verdict,
                reason=reason,
                contradiction_flags=contradiction.flags if contradiction.flags else [],
                extracted_features_a=features_a,
                extracted_features_b=features_b,
                template_labels=[template_a, template_b],
                relationship_type=RelationshipType.EQUIVALENT if verdict == Verdict.ACCEPT else RelationshipType.UNRELATED,
                confidence=confidence,
            ))
        except Exception as exc:
            log.warning("Phase3 no-LLM error on %s: %s", candidate.candidate_id, exc)
            decisions.append(Phase3Decision(
                candidate_id=candidate.candidate_id,
                verdict=Verdict.REVIEW,
                reason=f"Error: {exc}",
                confidence=0.0,
            ))

    return canonical, decisions


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(threshold: float, model: str, bankroll: float, limit: int, platforms: list[str], keyword: Optional[str] = None, no_llm: bool = False) -> None:
    t_start = time.perf_counter()

    # ── Connect ──────────────────────────────────────────────────────────────
    from algorithm.db import get_db, get_db_name, get_mongo_uri

    mongo_uri = get_mongo_uri()
    db = get_db()
    db_name = get_db_name()
    log.info("Connected to %s / %s", mongo_uri.split("@")[-1] if "@" in mongo_uri else mongo_uri, db_name)

    cols = db.list_collection_names()
    log.info("Collections: %s", cols)

    # ── Load questions ───────────────────────────────────────────────────────
    with_vectors, without_vectors = _load_questions_from_markets(db, platforms, limit, keyword)

    # ── Phase 2A: Embed new questions ────────────────────────────────────────
    if without_vectors:
        from algorithm.Phase_2.embedder import TransformerEmbedder

        log.info("Embedding %d new questions with %s ...", len(without_vectors), model)
        embedder = TransformerEmbedder(model_name=model)
        vectors = embedder.embed_batch([q.text for q in without_vectors])
        for q, vec in zip(without_vectors, vectors):
            q.vector = vec
        _save_vectors_to_markets(db, without_vectors)
    else:
        log.info("No new questions to embed")

    all_questions = with_vectors + without_vectors
    if not all_questions:
        log.warning("No questions loaded — stopping")
        return

    markets_present = set(q.market for q in all_questions)
    log.info("Loaded %d total questions from platforms: %s", len(all_questions), markets_present)

    if len(markets_present) < 2:
        log.warning("Need at least 2 platforms for cross-market pairs — only found: %s", markets_present)
        return

    # ── Phase 2B: Find candidate pairs ──────────────────────────────────────
    from algorithm.Phase_2.pipeline import ArbitragePipeline
    from algorithm.Phase_2.embedder import TransformerEmbedder

    pipeline = ArbitragePipeline(
        embedder=TransformerEmbedder(model_name=model),
        similarity_threshold=threshold,
    )
    phase2_candidates = pipeline.run(all_questions)
    log.info("Phase 2: %d candidate pairs at threshold %.2f", len(phase2_candidates), threshold)

    if not phase2_candidates:
        log.warning("No candidate pairs found — stopping")
        _print_summary(t_start, all_questions, markets_present, threshold, [], [], [], [])
        return

    _save_candidates_to_db(db, phase2_candidates)

    # ── Phase 3: LLM verification (or heuristic fallback) ────────────────────
    if no_llm:
        log.info("Phase 3: no-LLM mode — using embedding similarity + entity/template checks for %d candidates ...", len(phase2_candidates))
        canonical_candidates, decisions = _run_phase3_no_llm(phase2_candidates, similarity_threshold=threshold)
    else:
        log.info("Phase 3: validating %d candidates with LLM ...", len(phase2_candidates))
        canonical_candidates, decisions = asyncio.run(_run_phase3(phase2_candidates))

    from algorithm.Phase_3.models import Verdict

    accepted = sum(1 for d in decisions if d.verdict == Verdict.ACCEPT)
    rejected = sum(1 for d in decisions if d.verdict == Verdict.REJECT)
    review = sum(1 for d in decisions if d.verdict == Verdict.REVIEW)
    log.info("Phase 3: accepted=%d rejected=%d review=%d", accepted, rejected, review)

    # ── Phase 4: Arbitrage scoring ───────────────────────────────────────────
    from algorithm.Phase_4.adapters import filter_accepted
    from algorithm.Phase_4.engine import ArbitrageEngine, persist_signals

    matched_pairs = filter_accepted(canonical_candidates, decisions)
    log.info("Phase 4: scoring %d matched pairs ...", len(matched_pairs))

    arb_engine = ArbitrageEngine(bankroll=bankroll)
    signals = arb_engine.score_pairs(matched_pairs)
    log.info("Phase 4: %d signals generated", len(signals))

    if signals:
        persist_signals(signals)
        log.info("Persisted %d signals to MongoDB", len(signals))

    # ── Phase 5: Live validation ─────────────────────────────────────────────
    from algorithm.Phase_5.validator import TradeValidator, persist_validated

    log.info("Phase 5: validating %d signals ...", len(signals))
    validator = TradeValidator()
    validated = validator.validate_batch(signals)
    executable = [v for v in validated if v.executable]
    log.info("Phase 5: %d/%d executable", len(executable), len(validated))

    if validated:
        persist_validated(validated)
        log.info("Persisted %d validated opportunities to MongoDB", len(validated))

    _print_summary(
        t_start, all_questions, markets_present, threshold,
        phase2_candidates, decisions, signals, executable
    )


def _print_summary(t_start, all_questions, markets, threshold, candidates, decisions, signals, executable):
    from algorithm.Phase_3.models import Verdict

    elapsed = time.perf_counter() - t_start
    neg_count = sum(1 for p in candidates if p.has_potential_negation)
    high_conf = sum(1 for p in candidates if p.similarity_score >= 0.90)
    accepted = sum(1 for d in decisions if d.verdict == Verdict.ACCEPT) if decisions else 0
    rejected = sum(1 for d in decisions if d.verdict == Verdict.REJECT) if decisions else 0
    review = sum(1 for d in decisions if d.verdict == Verdict.REVIEW) if decisions else 0

    print(f"\n{'─'*60}")
    print(f"  Full Pipeline Summary")
    print(f"{'─'*60}")
    print(f"  Questions loaded       : {len(all_questions)}")
    print(f"  Platforms              : {', '.join(sorted(markets))}")
    print(f"  Phase 2 candidates     : {len(candidates)}  (≥{threshold:.0%} similarity)")
    print(f"    High confidence ≥90% : {high_conf}")
    print(f"    Negation flagged     : {neg_count}")
    print(f"  Phase 3 accepted       : {accepted}  (rejected={rejected}, review={review})")
    print(f"  Phase 4 signals        : {len(signals)}")
    print(f"  Phase 5 executable     : {len(executable)}")
    print(f"  Total time             : {elapsed:.2f}s")
    print(f"{'─'*60}")

    if executable:
        print("\n  Top executable opportunities:")
        for opp in executable[:5]:
            sig = opp.signal
            print(
                f"    {sig.pair_id[:40]:40s}  "
                f"spread={opp.live_spread:.4f}  "
                f"EV=${sig.expected_profit:.2f}  "
                f"size=${sig.recommended_size_usd:.0f}"
            )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full ArbIt pipeline (Phases 2-5)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--bankroll", type=float, default=10_000.0)
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"Max questions to load per platform (default: {DEFAULT_LIMIT})"
    )
    parser.add_argument(
        "--platform", nargs="+", default=["kalshi", "polymarket"],
        help="Platforms to include (default: kalshi polymarket)"
    )
    parser.add_argument(
        "--keyword", default=None,
        help="Filter questions by keyword (e.g. 'Bitcoin', 'Trump', 'election')"
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Skip LLM judge (use contradiction check + reranker only). "
             "Useful when DeepSeek/OpenAI API is unavailable."
    )
    args = parser.parse_args()
    run(
        threshold=args.threshold,
        model=args.model,
        bankroll=args.bankroll,
        limit=args.limit,
        platforms=args.platform,
        keyword=args.keyword,
        no_llm=args.no_llm,
    )


if __name__ == "__main__":
    main()
