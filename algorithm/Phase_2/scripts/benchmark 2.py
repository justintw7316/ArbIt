#!/usr/bin/env python3
"""Model benchmark for prediction market arbitrage candidate detection.

Evaluates semantic similarity quality across 6 real-world sectors with
ground truth labels. Compares multiple models and reports precision,
recall, separation quality, and F1 at each threshold.

Usage:
    poetry run python -m algorithm.Phase_2.scripts.benchmark
    poetry run python -m algorithm.Phase_2.scripts.benchmark --models all-mpnet-base-v2
    poetry run python -m algorithm.Phase_2.scripts.benchmark --sector politics
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from typing import List, Optional

from algorithm.Phase_2.embedder import TransformerEmbedder

# ---------------------------------------------------------------------------
# Ground truth dataset
# Each pair is labelled:
#   should_match=True  → genuinely the same event (arb candidate)
#   should_match=False → different events (should NOT be returned as candidate)
#   has_negation=True  → same event but semantically inverted (requires step 3)
# Difficulty: easy (obvious phrasing), medium (different words), hard (tricky)
# ---------------------------------------------------------------------------

@dataclass
class GroundTruthPair:
    id: str
    sector: str
    text_a: str
    text_b: str
    should_match: bool           # True = genuine arb candidate
    has_negation: bool = False   # True = same topic but inverted meaning
    difficulty: str = "medium"   # "easy" | "medium" | "hard"
    note: str = ""


GROUND_TRUTH: List[GroundTruthPair] = [

    # -----------------------------------------------------------------------
    # POLITICS
    # -----------------------------------------------------------------------
    GroundTruthPair(
        id="pol_01", sector="politics",
        text_a="Will Donald Trump win the 2024 US presidential election?",
        text_b="Does Trump become US president after the 2024 election?",
        should_match=True, difficulty="easy",
        note="same event, near-paraphrase",
    ),
    GroundTruthPair(
        id="pol_02", sector="politics",
        text_a="Will the US Senate pass immigration reform legislation in 2025?",
        text_b="Senate immigration bill approved before end of 2025?",
        should_match=True, difficulty="medium",
        note="same bill, rephrased",
    ),
    GroundTruthPair(
        id="pol_03", sector="politics",
        text_a="Will Joe Biden be the Democratic nominee in 2024?",
        text_b="Does the Democratic Party nominate Biden for 2024 president?",
        should_match=True, difficulty="easy",
        note="same event",
    ),
    GroundTruthPair(
        id="pol_04", sector="politics",
        text_a="Will Congress pass a government shutdown in October 2025?",
        text_b="US government avoids shutdown through October 2025?",
        should_match=True, difficulty="hard", has_negation=True,
        note="same event but one is the complement — negation trap",
    ),
    GroundTruthPair(
        id="pol_05", sector="politics",
        text_a="Will Trump be convicted in the hush money trial?",
        text_b="Will Trump be impeached by the House in 2025?",
        should_match=False, difficulty="hard",
        note="different legal proceedings — should NOT match",
    ),
    GroundTruthPair(
        id="pol_06", sector="politics",
        text_a="Will the UK hold a general election in 2024?",
        text_b="Will Labour win the UK general election 2024?",
        should_match=False, difficulty="hard",
        note="related but different questions — occurrence vs winner",
    ),
    GroundTruthPair(
        id="pol_07", sector="politics",
        text_a="Will Trump win the 2024 election?",
        text_b="Will Trump lose the 2024 election?",
        should_match=True, difficulty="easy", has_negation=True,
        note="same event, directly inverted — critical negation test",
    ),

    # -----------------------------------------------------------------------
    # GEOPOLITICS
    # -----------------------------------------------------------------------
    GroundTruthPair(
        id="geo_01", sector="geopolitics",
        text_a="Will Russia and Ukraine reach a ceasefire agreement in 2025?",
        text_b="Ukraine-Russia peace deal or ceasefire signed by end of 2025?",
        should_match=True, difficulty="medium",
        note="same event, rephrased",
    ),
    GroundTruthPair(
        id="geo_02", sector="geopolitics",
        text_a="Will China invade Taiwan before 2026?",
        text_b="Chinese military attack on Taiwan island before 2026?",
        should_match=True, difficulty="medium",
        note="same geopolitical event",
    ),
    GroundTruthPair(
        id="geo_03", sector="geopolitics",
        text_a="Will NATO expand to include new members in 2025?",
        text_b="New country joins NATO alliance in 2025?",
        should_match=True, difficulty="easy",
        note="same event",
    ),
    GroundTruthPair(
        id="geo_04", sector="geopolitics",
        text_a="Will China invade Taiwan before 2026?",
        text_b="Will North Korea conduct a nuclear test in 2025?",
        should_match=False, difficulty="medium",
        note="both geopolitics Asia but entirely different events",
    ),
    GroundTruthPair(
        id="geo_05", sector="geopolitics",
        text_a="Will Russia withdraw troops from Ukraine in 2025?",
        text_b="Will Russia escalate its military campaign in Ukraine in 2025?",
        should_match=True, difficulty="hard", has_negation=True,
        note="same conflict, opposite directions — negation trap",
    ),

    # -----------------------------------------------------------------------
    # CRYPTO / DIGITAL ASSETS
    # -----------------------------------------------------------------------
    GroundTruthPair(
        id="crt_01", sector="crypto",
        text_a="Will Bitcoin exceed $150,000 by end of 2025?",
        text_b="BTC price surpasses $150k USD before January 2026?",
        should_match=True, difficulty="easy",
        note="same threshold, same timeframe",
    ),
    GroundTruthPair(
        id="crt_02", sector="crypto",
        text_a="Will Ethereum reach $10,000 before 2026?",
        text_b="ETH hits $10k USD by December 2025?",
        should_match=True, difficulty="easy",
        note="same asset, same threshold",
    ),
    GroundTruthPair(
        id="crt_03", sector="crypto",
        text_a="Will a spot Bitcoin ETF be approved in the US by 2025?",
        text_b="SEC approves BTC spot exchange-traded fund before 2026?",
        should_match=True, difficulty="medium",
        note="same regulatory event",
    ),
    GroundTruthPair(
        id="crt_04", sector="crypto",
        text_a="Will Bitcoin exceed $150,000 by end of 2025?",
        text_b="Will Ethereum reach $10,000 before 2026?",
        should_match=False, difficulty="hard",
        note="different assets, different thresholds — classic false positive risk",
    ),
    GroundTruthPair(
        id="crt_05", sector="crypto",
        text_a="Will Bitcoin drop below $50,000 in 2025?",
        text_b="Will Bitcoin exceed $150,000 by end of 2025?",
        should_match=True, difficulty="hard", has_negation=True,
        note="same asset, opposite price directions — negation trap",
    ),
    GroundTruthPair(
        id="crt_06", sector="crypto",
        text_a="Will Solana (SOL) flip Ethereum by market cap in 2025?",
        text_b="SOL market cap surpasses ETH before 2026?",
        should_match=True, difficulty="medium",
        note="same milestone, different phrasing",
    ),

    # -----------------------------------------------------------------------
    # SPORTS
    # -----------------------------------------------------------------------
    GroundTruthPair(
        id="spt_01", sector="sports",
        text_a="Will the Kansas City Chiefs win Super Bowl LIX in 2025?",
        text_b="Kansas City Chiefs Super Bowl champions for 2025 season?",
        should_match=True, difficulty="easy",
        note="same team, same event",
    ),
    GroundTruthPair(
        id="spt_02", sector="sports",
        text_a="Will Novak Djokovic win Wimbledon 2025?",
        text_b="Djokovic takes the 2025 Wimbledon championship?",
        should_match=True, difficulty="easy",
        note="same player, same tournament",
    ),
    GroundTruthPair(
        id="spt_03", sector="sports",
        text_a="Will Argentina win the 2026 FIFA World Cup?",
        text_b="Does Brazil take the FIFA World Cup trophy in 2026?",
        should_match=False, difficulty="medium",
        note="same tournament, different teams — should NOT match",
    ),
    GroundTruthPair(
        id="spt_04", sector="sports",
        text_a="Will the LA Lakers win the NBA championship in 2025?",
        text_b="Will LeBron James retire before the 2025 NBA Finals?",
        should_match=False, difficulty="hard",
        note="related franchise/player but entirely different events",
    ),
    GroundTruthPair(
        id="spt_05", sector="sports",
        text_a="Will Real Madrid win the 2025 UEFA Champions League?",
        text_b="Champions League 2025 winner is Real Madrid?",
        should_match=True, difficulty="easy",
        note="paraphrase",
    ),

    # -----------------------------------------------------------------------
    # MACROECONOMICS / FINANCE
    # -----------------------------------------------------------------------
    GroundTruthPair(
        id="eco_01", sector="economics",
        text_a="Will the Federal Reserve cut interest rates in 2025?",
        text_b="Fed reduces benchmark rate during calendar year 2025?",
        should_match=True, difficulty="medium",
        note="same policy action",
    ),
    GroundTruthPair(
        id="eco_02", sector="economics",
        text_a="Will US inflation (CPI) drop below 2% in 2025?",
        text_b="Consumer Price Index falls under 2 percent by end of 2025?",
        should_match=True, difficulty="medium",
        note="same macro indicator, same threshold",
    ),
    GroundTruthPair(
        id="eco_03", sector="economics",
        text_a="Will the US enter a recession in 2025?",
        text_b="Does the United States experience negative GDP growth in 2025?",
        should_match=True, difficulty="medium",
        note="recession = two quarters negative GDP",
    ),
    GroundTruthPair(
        id="eco_04", sector="economics",
        text_a="Will the Federal Reserve cut interest rates in 2025?",
        text_b="Will the Federal Reserve raise interest rates in 2025?",
        should_match=True, difficulty="medium", has_negation=True,
        note="same entity, opposite policy action — critical negation test",
    ),
    GroundTruthPair(
        id="eco_05", sector="economics",
        text_a="Will the US stock market (S&P 500) reach 7,000 points by 2026?",
        text_b="Will crude oil price exceed $120 per barrel in 2025?",
        should_match=False, difficulty="medium",
        note="different asset classes entirely",
    ),
    GroundTruthPair(
        id="eco_06", sector="economics",
        text_a="Will the ECB cut rates in 2025?",
        text_b="Will the Federal Reserve cut rates in 2025?",
        should_match=False, difficulty="hard",
        note="same action type but different central banks — tricky false positive",
    ),

    # -----------------------------------------------------------------------
    # SCIENCE / TECHNOLOGY
    # -----------------------------------------------------------------------
    GroundTruthPair(
        id="sci_01", sector="science",
        text_a="Will SpaceX Starship successfully reach orbit in 2025?",
        text_b="SpaceX Starship completes an orbital mission before 2026?",
        should_match=True, difficulty="easy",
        note="same milestone",
    ),
    GroundTruthPair(
        id="sci_02", sector="science",
        text_a="Will OpenAI release GPT-5 before the end of 2025?",
        text_b="Is GPT-5 publicly available by December 31, 2025?",
        should_match=True, difficulty="easy",
        note="same product release event",
    ),
    GroundTruthPair(
        id="sci_03", sector="science",
        text_a="Will a human land on the Moon before 2027?",
        text_b="Crewed lunar landing mission success before 2027?",
        should_match=True, difficulty="medium",
        note="same milestone",
    ),
    GroundTruthPair(
        id="sci_04", sector="science",
        text_a="Will OpenAI release GPT-5 before the end of 2025?",
        text_b="Will Google release Gemini 3.0 by end of 2025?",
        should_match=False, difficulty="hard",
        note="same category (AI model release) but different companies/products",
    ),
    GroundTruthPair(
        id="sci_05", sector="science",
        text_a="Will the US ban TikTok in 2025?",
        text_b="TikTok remains available in the United States through 2025?",
        should_match=True, difficulty="hard", has_negation=True,
        note="same event, complementary framing — negation trap",
    ),
]


# ---------------------------------------------------------------------------
# Evaluation engine
# ---------------------------------------------------------------------------

def compute_similarity(embedder: TransformerEmbedder, pairs: List[GroundTruthPair]) -> List[float]:
    """Embed all texts in two batch calls, return per-pair similarity."""
    import numpy as np
    texts_a = [p.text_a for p in pairs]
    texts_b = [p.text_b for p in pairs]
    vecs_a = np.array(embedder.embed_batch(texts_a), dtype=np.float32)
    vecs_b = np.array(embedder.embed_batch(texts_b), dtype=np.float32)
    # dot product == cosine similarity for L2-normalised vectors
    return [float(np.dot(vecs_a[i], vecs_b[i])) for i in range(len(pairs))]


def evaluate(
    model_name: str,
    pairs: List[GroundTruthPair],
    thresholds: List[float],
) -> dict:
    """Embed, score, and compute precision/recall/F1 for one model."""
    print(f"\n  Loading {model_name} ...")
    t0 = time.perf_counter()
    embedder = TransformerEmbedder(model_name=model_name)
    scores = compute_similarity(embedder, pairs)
    elapsed = time.perf_counter() - t0

    true_labels = [p.should_match for p in pairs]
    pos_scores = [s for s, l in zip(scores, true_labels) if l]
    neg_scores = [s for s, l in zip(scores, true_labels) if not l]

    results_by_threshold = {}
    for thr in thresholds:
        preds = [s >= thr for s in scores]
        tp = sum(p and l for p, l in zip(preds, true_labels))
        fp = sum(p and not l for p, l in zip(preds, true_labels))
        fn = sum(not p and l for p, l in zip(preds, true_labels))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        results_by_threshold[thr] = dict(precision=precision, recall=recall, f1=f1, tp=tp, fp=fp, fn=fn)

    # Negation pair analysis
    neg_pairs = [p for p in pairs if p.has_negation]
    neg_pair_scores = {p.id: scores[pairs.index(p)] for p in neg_pairs}

    best_f1_thr = max(thresholds, key=lambda t: results_by_threshold[t]["f1"])

    return dict(
        model=model_name,
        elapsed=elapsed,
        scores=scores,
        mean_pos=sum(pos_scores) / len(pos_scores) if pos_scores else 0,
        mean_neg=sum(neg_scores) / len(neg_scores) if neg_scores else 0,
        separation=((sum(pos_scores) / len(pos_scores)) - (sum(neg_scores) / len(neg_scores))) if pos_scores and neg_scores else 0,
        by_threshold=results_by_threshold,
        best_f1_thr=best_f1_thr,
        neg_pair_scores=neg_pair_scores,
    )


def print_model_results(result: dict, pairs: List[GroundTruthPair], thresholds: List[float]) -> None:
    model = result["model"]
    print(f"\n{'─'*68}")
    print(f"  Model: {model}")
    print(f"  Embed time: {result['elapsed']:.2f}s")
    print(f"  Mean sim (true pairs):  {result['mean_pos']:.4f}")
    print(f"  Mean sim (false pairs): {result['mean_neg']:.4f}")
    print(f"  Separation gap:         {result['separation']:.4f}  (higher = cleaner separation)")

    print(f"\n  {'Threshold':>10}  {'Precision':>10}  {'Recall':>8}  {'F1':>8}  {'TP':>4}  {'FP':>4}  {'FN':>4}")
    print(f"  {'─'*10}  {'─'*10}  {'─'*8}  {'─'*8}  {'─'*4}  {'─'*4}  {'─'*4}")
    for thr in thresholds:
        r = result["by_threshold"][thr]
        best = " ← best F1" if thr == result["best_f1_thr"] else ""
        print(f"  {thr:>10.2f}  {r['precision']:>10.3f}  {r['recall']:>8.3f}  {r['f1']:>8.3f}  {r['tp']:>4}  {r['fp']:>4}  {r['fn']:>4}{best}")

    # Per-pair detail at best threshold
    best_thr = result["best_f1_thr"]
    scores = result["scores"]
    print(f"\n  Per-pair scores at best threshold ({best_thr}):")
    sector_groups: dict = {}
    for pair, score in zip(pairs, scores):
        sector_groups.setdefault(pair.sector, []).append((pair, score))

    for sector, items in sorted(sector_groups.items()):
        print(f"\n    [{sector.upper()}]")
        for pair, score in items:
            predicted = score >= best_thr
            actual = pair.should_match
            status = "✓" if predicted == actual else "✗ WRONG"
            neg_flag = " [NEG]" if pair.has_negation else ""
            match_label = "MATCH" if actual else "NO-MATCH"
            diff = f"({pair.difficulty})"
            print(f"      {status} {score:.4f}  [{match_label}]{neg_flag}  {diff}")
            print(f"           A: {pair.text_a[:70]}")
            print(f"           B: {pair.text_b[:70]}")

    # Negation analysis
    if result["neg_pair_scores"]:
        print(f"\n  Negation pairs (step 3 must verify these):")
        for pid, score in result["neg_pair_scores"].items():
            pair = next(p for p in pairs if p.id == pid)
            above = "RETRIEVED" if score >= best_thr else "MISSED"
            print(f"    [{above} at {best_thr}] score={score:.4f}  {pair.text_a[:55]!r}")
            print(f"                        vs {pair.text_b[:55]!r}")


def print_comparison_table(results: List[dict], thresholds: List[float]) -> None:
    print(f"\n{'='*68}")
    print("  MODEL COMPARISON SUMMARY")
    print("=" * 68)
    print(f"  {'Model':<40}  {'Sep':>6}  {'Best-F1':>8}  {'@thr':>6}  {'Time':>6}")
    print(f"  {'─'*40}  {'─'*6}  {'─'*8}  {'─'*6}  {'─'*6}")
    for r in results:
        best_f1 = r["by_threshold"][r["best_f1_thr"]]["f1"]
        print(
            f"  {r['model']:<40}  {r['separation']:>6.4f}  {best_f1:>8.3f}  {r['best_f1_thr']:>6.2f}  {r['elapsed']:>5.1f}s"
        )
    winner = max(results, key=lambda r: r["by_threshold"][r["best_f1_thr"]]["f1"])
    print(f"\n  → Best model: {winner['model']}")
    print(f"    Recommendation: use threshold {winner['best_f1_thr']:.2f} for step 3 input")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark embedding models for prediction market arb")
    parser.add_argument(
        "--models", nargs="+",
        default=["all-mpnet-base-v2", "paraphrase-mpnet-base-v2", "multi-qa-mpnet-base-dot-v1"],
        help="Model names to compare",
    )
    parser.add_argument(
        "--thresholds", nargs="+", type=float,
        default=[0.70, 0.75, 0.80, 0.85, 0.90],
        help="Similarity thresholds to evaluate",
    )
    parser.add_argument(
        "--sector", type=str, default=None,
        help="Filter to a specific sector (politics, geopolitics, crypto, sports, economics, science)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show per-pair detail for every model (default: only show for first model)",
    )
    args = parser.parse_args()

    pairs = GROUND_TRUTH
    if args.sector:
        pairs = [p for p in GROUND_TRUTH if p.sector == args.sector]
        if not pairs:
            print(f"No pairs found for sector {args.sector!r}")
            sys.exit(1)

    n_match = sum(1 for p in pairs if p.should_match)
    n_neg = sum(1 for p in pairs if p.has_negation)
    print(f"\n{'='*68}")
    print("  PREDICTION MARKET EMBEDDING BENCHMARK")
    print("=" * 68)
    print(f"  Total pairs:          {len(pairs)}")
    print(f"  True arb candidates:  {n_match}")
    print(f"  False pairs:          {len(pairs) - n_match}")
    print(f"  Negation traps:       {n_neg}")
    print(f"  Sectors:              {sorted(set(p.sector for p in pairs))}")
    print(f"  Models to compare:    {args.models}")
    print(f"  Thresholds:           {args.thresholds}")

    all_results = []
    for i, model in enumerate(args.models):
        result = evaluate(model, pairs, args.thresholds)
        all_results.append(result)
        if args.verbose or i == 0:
            print_model_results(result, pairs, args.thresholds)

    if len(all_results) > 1:
        # Show detail for remaining models without per-pair breakdown
        for result in all_results[1:]:
            if not args.verbose:
                model = result["model"]
                best_f1 = result["by_threshold"][result["best_f1_thr"]]["f1"]
                print(f"\n{'─'*68}")
                print(f"  Model: {model}  |  elapsed: {result['elapsed']:.2f}s")
                print(f"  Mean sim (true/false): {result['mean_pos']:.4f} / {result['mean_neg']:.4f}  sep={result['separation']:.4f}")
                print(f"  Best F1={best_f1:.3f} @ threshold={result['best_f1_thr']}")
                for thr in args.thresholds:
                    r = result["by_threshold"][thr]
                    best = " ←" if thr == result["best_f1_thr"] else ""
                    print(f"    thr={thr:.2f}  P={r['precision']:.3f}  R={r['recall']:.3f}  F1={r['f1']:.3f}  TP={r['tp']}  FP={r['fp']}  FN={r['fn']}{best}")

        print_comparison_table(all_results, args.thresholds)


if __name__ == "__main__":
    main()
