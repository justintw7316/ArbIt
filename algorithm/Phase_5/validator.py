"""Phase 5 — Live Validation Orchestrator.

Takes ArbitrageSignal objects from Phase 4 and either promotes them
to executable ValidatedOpportunity objects or rejects them.

Validation steps:
    1. Re-check live prices → confirm spread still exists
    2. Check direction still agrees with Phase 4 thesis
    3. Check liquidity → can we execute at recommended size?
    4. Check price correlation → is this really the same event?
    5. Build concrete trade actions if all checks pass
"""

from __future__ import annotations

import logging
from datetime import datetime

from algorithm.Phase_4.config import MIN_SPREAD
from algorithm.Phase_4.models import ArbitrageSignal, Direction, Platform
from algorithm.Phase_5.models import TradeAction, ValidatedOpportunity
from algorithm.Phase_5.price_checker import check_spread_still_exists, fetch_live_price
from algorithm.Phase_5.liquidity import adjust_size_for_liquidity, check_liquidity
from algorithm.Phase_5.correlation import compute_price_correlation

logger = logging.getLogger(__name__)


class TradeValidator:
    """Validates Phase 4 signals against live market conditions."""

    def __init__(
        self,
        min_spread: float = MIN_SPREAD,
        min_correlation: float = 0.60,
    ) -> None:
        self.min_spread = min_spread
        self.min_correlation = min_correlation

    def validate(self, signal: ArbitrageSignal) -> ValidatedOpportunity:
        """Run all validation checks on a single signal."""
        rejection_reasons: list[str] = []

        # 1. Live price check
        live_a = fetch_live_price(signal.platform_a, signal.market_a_id)
        live_b = fetch_live_price(signal.platform_b, signal.market_b_id)

        live_fetch_ok = True
        if live_a is None:
            live_fetch_ok = False
            live_a = signal.price_a
            rejection_reasons.append(
                f"Could not fetch live price for {signal.platform_a.value}/{signal.market_a_id}"
            )
        if live_b is None:
            live_fetch_ok = False
            live_b = signal.price_b
            rejection_reasons.append(
                f"Could not fetch live price for {signal.platform_b.value}/{signal.market_b_id}"
            )

        live_spread, spread_ok = check_spread_still_exists(
            signal, live_a, live_b, self.min_spread
        )

        if not spread_ok:
            rejection_reasons.append(
                f"Spread vanished: {live_spread:.4f} < {self.min_spread:.4f}"
            )

        # Direction must still agree with the Phase 4 thesis
        live_direction = (
            Direction.BUY_B_SELL_A if live_a >= live_b else Direction.BUY_A_SELL_B
        )
        direction_ok = live_direction == signal.direction
        if not direction_ok:
            rejection_reasons.append(
                f"Direction reversed live: phase4={signal.direction.value}, "
                f"live={live_direction.value}"
            )

        # 2. Liquidity check
        liq_a, liq_b = self._get_liquidity(signal)
        liq_check = check_liquidity(liq_a, liq_b, signal.recommended_size_usd)

        if not liq_check.sufficient:
            rejection_reasons.append(f"Liquidity: {liq_check.reason}")

        adjusted_size = adjust_size_for_liquidity(
            signal.recommended_size_usd, liq_a, liq_b
        )

        # 3. Price correlation / vector testing
        corr, corr_ok = compute_price_correlation(
            signal.platform_a.value,
            signal.market_a_id,
            signal.platform_b.value,
            signal.market_b_id,
        )

        if not corr_ok and corr != 0.0:
            rejection_reasons.append(f"Low price correlation: {corr:.3f}")

        # Final executable decision
        executable = (
            spread_ok
            and direction_ok
            and liq_check.sufficient
            and (corr_ok or corr == 0.0)
            and adjusted_size > 0
        )
        actions: list[TradeAction] = []
        if executable:
            actions = self._build_actions(signal, live_a, live_b, adjusted_size)

        result = ValidatedOpportunity(
            signal=signal,
            live_price_a=live_a,
            live_price_b=live_b,
            live_spread=live_spread,
            spread_still_exists=spread_ok,
            liquidity_ok=liq_check.sufficient,
            price_correlation=corr,
            correlation_ok=corr_ok,
            executable=executable,
            rejection_reasons=rejection_reasons,
            actions=actions,
            validated_at=datetime.utcnow(),
        )

        if executable:
            logger.info(
                "EXECUTABLE: %s | spread=%.4f size=$%.0f corr=%.3f",
                signal.pair_id,
                live_spread,
                adjusted_size,
                corr,
            )
        else:
            logger.info("REJECTED: %s | reasons: %s", signal.pair_id, rejection_reasons)

        return result

    def validate_batch(
        self, signals: list[ArbitrageSignal]
    ) -> list[ValidatedOpportunity]:
        """Validate a list of signals."""
        results = [self.validate(sig) for sig in signals]
        n_exec = sum(1 for r in results if r.executable)
        logger.info("Phase 5 complete: %d/%d executable", n_exec, len(results))
        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_liquidity(self, signal: ArbitrageSignal) -> tuple[float, float]:
        """Look up current liquidity from the markets collection."""
        try:
            from algorithm.db import get_db, MARKETS_COL

            db = get_db()
            col = db[MARKETS_COL]
            doc_a = col.find_one({
                "platform": signal.platform_a.value,
                "market_id": signal.market_a_id,
            })
            doc_b = col.find_one({
                "platform": signal.platform_b.value,
                "market_id": signal.market_b_id,
            })
            liq_a = float(doc_a.get("liquidity", 0)) if doc_a else 0
            liq_b = float(doc_b.get("liquidity", 0)) if doc_b else 0
            return liq_a, liq_b
        except Exception as exc:
            logger.debug("Could not fetch liquidity from DB: %s", exc)
            return 0, 0

    @staticmethod
    def _build_actions(
        signal: ArbitrageSignal,
        live_a: float,
        live_b: float,
        size: float,
    ) -> list[TradeAction]:
        """Build concrete trade actions based on signal direction."""
        half = round(size / 2, 2)

        if signal.direction == Direction.BUY_B_SELL_A:
            # B is cheap: buy YES on B, buy NO on A
            return [
                TradeAction(
                    platform=signal.platform_b,
                    market_id=signal.market_b_id,
                    side="yes",
                    amount_usd=half,
                    limit_price=round(live_b + 0.01, 4),
                ),
                TradeAction(
                    platform=signal.platform_a,
                    market_id=signal.market_a_id,
                    side="no",
                    amount_usd=half,
                    limit_price=round((1 - live_a) + 0.01, 4),
                ),
            ]
        else:
            # A is cheap: buy YES on A, buy NO on B
            return [
                TradeAction(
                    platform=signal.platform_a,
                    market_id=signal.market_a_id,
                    side="yes",
                    amount_usd=half,
                    limit_price=round(live_a + 0.01, 4),
                ),
                TradeAction(
                    platform=signal.platform_b,
                    market_id=signal.market_b_id,
                    side="no",
                    amount_usd=half,
                    limit_price=round((1 - live_b) + 0.01, 4),
                ),
            ]


def persist_validated(opportunities: list[ValidatedOpportunity]) -> int:
    """Store validated opportunities in MongoDB."""
    if not opportunities:
        return 0
    from algorithm.db import get_db, VALIDATED_COL

    db = get_db()
    col = db[VALIDATED_COL]
    for opp in opportunities:
        col.update_one(
            {"signal.pair_id": opp.signal.pair_id},
            {"$set": opp.model_dump(mode="json")},
            upsert=True,
        )
    return len(opportunities)
