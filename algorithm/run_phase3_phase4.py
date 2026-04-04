"""Run Phase 3 → Phase 4 on existing candidate_pairs in MongoDB.

Reads from:   candidate_pairs  (written by Phase 2)
Writes to:    phase3_decisions  (new collection — one doc per pair)
              signals           (Phase 4 output)
              validated_opportunities (Phase 5 output)

Usage:
    poetry run python -m algorithm.run_phase3_phase4
    poetry run python -m algorithm.run_phase3_phase4 --limit 500 --batch 100
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone

from pathlib import Path
from dotenv import load_dotenv

# Try backend/.env first (where MONGO_URI lives), then default .env
_repo_root = Path(__file__).resolve().parent.parent
load_dotenv(_repo_root / "backend" / ".env")
load_dotenv()  # fallback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Reconstruct Phase2 objects from MongoDB docs ──────────────────────────────

def _doc_to_phase2_pair(doc: dict):
    """Rebuild a Phase2 CandidatePair from a candidate_pairs MongoDB document."""
    from algorithm.Phase_2.models import CandidatePair, MarketQuestion

    def _make_question(platform: str, qid: str, text: str, price: float, end_date=None) -> MarketQuestion:
        metadata: dict = {
            "market_id": qid,
            "prices": {"Yes": price, "No": round(1.0 - price, 6)},
            "outcomes": ["Yes", "No"],
        }
        if end_date:
            metadata["close_time"] = end_date
        return MarketQuestion(
            id=qid,
            text=text,
            market=platform,
            price=float(price),
            metadata=metadata,
        )

    qa = _make_question(
        doc["market_a"],
        doc["question_id_a"],
        doc.get("text_a", ""),
        float(doc.get("price_a", 0.5)),
        doc.get("end_date_a"),
    )
    qb = _make_question(
        doc["market_b"],
        doc["question_id_b"],
        doc.get("text_b", ""),
        float(doc.get("price_b", 0.5)),
        doc.get("end_date_b"),
    )
    return CandidatePair(
        id=doc["id"],
        question_a=qa,
        question_b=qb,
        similarity_score=float(doc.get("similarity_score", 0.7)),
        has_potential_negation=bool(doc.get("has_potential_negation", False)),
        negation_tokens=list(doc.get("negation_tokens") or []),
    )


# ── Phase 3 (no-LLM heuristic) ───────────────────────────────────────────────

def _run_phase3_no_llm(phase2_pairs, similarity_threshold: float = 0.80):
    from algorithm.Phase_3.adapters import phase2_candidate_to_canonical
    from algorithm.Phase_3.classifier import classify_pair
    from algorithm.Phase_3.contradictions import check_contradictions
    from algorithm.Phase_3.extractor import extract_features
    from algorithm.Phase_3.models import Phase3Decision, RelationshipType, Verdict

    canonical = [phase2_candidate_to_canonical(c) for c in phase2_pairs]
    sim_map = {
        phase2_candidate_to_canonical(c).candidate_id: c.similarity_score
        for c in phase2_pairs
    }
    decisions = []
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
                reason = f"Structural: {'; '.join(contradiction.flags[:2])}"
                confidence = 0.0
            elif embedding_sim >= similarity_threshold:
                verdict = Verdict.ACCEPT
                reason = f"sim={embedding_sim:.3f} >= {similarity_threshold}"
                confidence = round(float(embedding_sim), 4)
            else:
                verdict = Verdict.REJECT
                reason = f"sim={embedding_sim:.3f} < {similarity_threshold}"
                confidence = 0.0

            decisions.append(Phase3Decision(
                candidate_id=candidate.candidate_id,
                verdict=verdict,
                reason=reason,
                contradiction_flags=contradiction.flags or [],
                extracted_features_a=features_a,
                extracted_features_b=features_b,
                template_labels=[template_a, template_b],
                relationship_type=RelationshipType.EQUIVALENT if verdict == Verdict.ACCEPT else RelationshipType.UNRELATED,
                confidence=confidence,
            ))
        except Exception as exc:
            log.warning("Phase3 error on %s: %s", candidate.candidate_id, exc)
            decisions.append(Phase3Decision(
                candidate_id=candidate.candidate_id,
                verdict=Verdict.REVIEW,
                reason=f"Error: {exc}",
                confidence=0.0,
            ))
    return canonical, decisions


# ── Persist Phase 3 decisions to new collection ───────────────────────────────

def _persist_phase3_decisions(db, decisions, canonical_candidates) -> int:
    """Write Phase 3 decisions to phase3_decisions collection."""
    col = db["phase3_decisions"]
    col.create_index("candidate_id", unique=True)

    # Build a map from candidate_id → canonical candidate for extra context
    cand_map = {c.candidate_id: c for c in canonical_candidates}

    count = 0
    for d in decisions:
        cand = cand_map.get(d.candidate_id)
        doc = {
            "candidate_id": d.candidate_id,
            "verdict": d.verdict.value,
            "reason": d.reason,
            "confidence": d.confidence,
            "contradiction_flags": d.contradiction_flags,
            "relationship_type": d.relationship_type.value if d.relationship_type else None,
            "template_labels": [t.value if hasattr(t, "value") else str(t) for t in (d.template_labels or [])],
            "processed_at": datetime.now(timezone.utc),
        }
        if cand:
            doc["question_a"] = cand.market_a.question
            doc["question_b"] = cand.market_b.question
            doc["platform_a"] = cand.market_a.platform
            doc["platform_b"] = cand.market_b.platform
            doc["embedding_similarity"] = cand.embedding_similarity

        col.update_one({"candidate_id": d.candidate_id}, {"$set": doc}, upsert=True)
        count += 1

    log.info("Persisted %d Phase 3 decisions to phase3_decisions", count)
    return count


# ── Main ──────────────────────────────────────────────────────────────────────

def run(limit: int, batch: int, threshold: float, bankroll: float) -> None:
    t_start = time.perf_counter()

    from algorithm.db import get_db

    db = get_db()
    log.info("Connected. candidate_pairs: %d", db["candidate_pairs"].count_documents({}))

    # ── Load candidate pairs from MongoDB ────────────────────────────────────
    total = db["candidate_pairs"].count_documents({})
    effective_limit = min(limit, total)
    log.info("Loading %d candidate pairs (total=%d)...", effective_limit, total)

    raw_docs = list(
        db["candidate_pairs"]
        .find({}, {"_id": 0})
        .sort("similarity_score", -1)
        .limit(effective_limit)
    )
    log.info("Loaded %d docs", len(raw_docs))

    phase2_pairs = []
    for doc in raw_docs:
        try:
            phase2_pairs.append(_doc_to_phase2_pair(doc))
        except Exception as e:
            log.warning("Skipping malformed pair %s: %s", doc.get("id"), e)

    log.info("Reconstructed %d Phase2 CandidatePairs", len(phase2_pairs))

    # ── Phase 3 (batch processing) ───────────────────────────────────────────
    log.info("Running Phase 3 (no-LLM, threshold=%.2f) in batches of %d...", threshold, batch)

    all_canonical = []
    all_decisions = []
    accepted_count = 0
    rejected_count = 0

    for i in range(0, len(phase2_pairs), batch):
        chunk = phase2_pairs[i: i + batch]
        canonical, decisions = _run_phase3_no_llm(chunk, similarity_threshold=threshold)
        all_canonical.extend(canonical)
        all_decisions.extend(decisions)

        from algorithm.Phase_3.models import Verdict
        acc = sum(1 for d in decisions if d.verdict == Verdict.ACCEPT)
        rej = sum(1 for d in decisions if d.verdict == Verdict.REJECT)
        accepted_count += acc
        rejected_count += rej
        log.info(
            "  Batch %d-%d: accepted=%d rejected=%d (running: acc=%d rej=%d)",
            i + 1, i + len(chunk), acc, rej, accepted_count, rejected_count,
        )

    log.info("Phase 3 complete: %d accepted, %d rejected of %d", accepted_count, rejected_count, len(phase2_pairs))

    # ── Save Phase 3 decisions to new collection ─────────────────────────────
    _persist_phase3_decisions(db, all_decisions, all_canonical)

    # ── Phase 4: Arbitrage scoring ───────────────────────────────────────────
    from algorithm.Phase_4.adapters import filter_accepted
    from algorithm.Phase_4.engine import ArbitrageEngine, persist_signals

    matched_pairs = filter_accepted(all_canonical, all_decisions)
    log.info("Phase 4: scoring %d matched pairs...", len(matched_pairs))

    arb_engine = ArbitrageEngine(bankroll=bankroll)
    signals = arb_engine.score_pairs(matched_pairs)
    log.info("Phase 4: %d signals generated", len(signals))

    if signals:
        persist_signals(signals)

    # ── Phase 5: Live validation ─────────────────────────────────────────────
    from algorithm.Phase_5.validator import TradeValidator, persist_validated

    log.info("Phase 5: validating %d signals...", len(signals))
    validator = TradeValidator()
    validated = validator.validate_batch(signals)
    executable = [v for v in validated if v.executable]
    log.info("Phase 5: %d/%d executable", len(executable), len(validated))

    if validated:
        persist_validated(validated)

    # ── Summary ──────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - t_start
    print(f"\n{'─'*60}")
    print(f"  Phase 3 → 4 → 5 Summary")
    print(f"{'─'*60}")
    print(f"  Candidate pairs loaded : {len(phase2_pairs)}")
    print(f"  Phase 3 accepted       : {accepted_count}")
    print(f"  Phase 3 rejected       : {rejected_count}")
    print(f"  Phase 4 signals        : {len(signals)}")
    print(f"  Phase 5 executable     : {len(executable)}")
    print(f"  Total time             : {elapsed:.1f}s")
    print(f"{'─'*60}")

    if executable:
        print("\n  Top opportunities:")
        for opp in executable[:5]:
            sig = opp.signal
            print(
                f"    spread={opp.live_spread:.4f}  EV=${sig.expected_profit:.2f}"
                f"  size=${sig.recommended_size_usd:.0f}"
                f"  [{sig.platform_a}↔{sig.platform_b}]"
            )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 3 → 4 → 5 on existing candidate_pairs")
    parser.add_argument("--limit", type=int, default=10_000, help="Max candidate pairs to process")
    parser.add_argument("--batch", type=int, default=200, help="Phase 3 batch size")
    parser.add_argument("--threshold", type=float, default=0.80, help="Phase 3 acceptance similarity threshold")
    parser.add_argument("--bankroll", type=float, default=10_000.0, help="Kelly bankroll in USD")
    args = parser.parse_args()
    run(limit=args.limit, batch=args.batch, threshold=args.threshold, bankroll=args.bankroll)


if __name__ == "__main__":
    main()
