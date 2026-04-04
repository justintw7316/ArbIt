"""Kelly criterion position sizing for Phase 4 arbitrage trades.

Full Kelly is famously aggressive, so we default to half-Kelly
(KELLY_FRACTION = 0.5) for practical use.
"""

from __future__ import annotations

from algorithm.Phase_4.config import KELLY_FRACTION, MAX_POSITION_FRACTION


def kelly_size(
    convergence_prob: float,
    spread: float,
    bankroll: float = 10_000.0,
    kelly_frac: float = KELLY_FRACTION,
    max_frac: float = MAX_POSITION_FRACTION,
    reward_per_dollar: float | None = None,
    risk_per_dollar: float | None = None,
    match_quality: float = 1.0,
) -> tuple[float, float]:
    """Compute recommended position size in USD.

    Parameters
    ----------
    convergence_prob : P(spread converges) from regression model
    spread           : displayed raw spread
    bankroll         : total capital available
    kelly_frac       : fraction of full Kelly to use (0.5 = half-Kelly)
    max_frac         : hard cap on position as fraction of bankroll
    reward_per_dollar: estimated capturable arbitrage per $ risked
    risk_per_dollar  : estimated adverse move per $ risked
    match_quality    : semantic / structural match quality in [0, 1]

    Returns
    -------
    (kelly_f, position_usd)
    """
    if spread <= 0 or convergence_prob <= 0 or bankroll <= 0:
        return 0.0, 0.0

    reward = max(reward_per_dollar if reward_per_dollar is not None else spread, 0.0)
    risk = max(risk_per_dollar if risk_per_dollar is not None else spread * 0.50, 1e-6)

    fee_estimate = 0.02
    reward_after_cost = max(reward - fee_estimate, 0.0)
    if reward_after_cost <= 0:
        return 0.0, 0.0

    # Penalize weakly-matched opportunities before sizing
    p = max(0.0, min(0.99, convergence_prob * (0.50 + 0.50 * max(0.0, min(1.0, match_quality)))))
    q = 1.0 - p

    b = reward_after_cost / risk
    if b <= 0:
        return 0.0, 0.0

    f_star = (p * b - q) / b
    f_star = max(f_star, 0.0)

    f_adj = f_star * kelly_frac
    f_adj = min(f_adj, max_frac)

    position = round(f_adj * bankroll, 2)
    return round(f_adj, 6), position


def expected_value(
    convergence_prob: float,
    spread: float,
    position_usd: float,
    reward_per_dollar: float | None = None,
    risk_per_dollar: float | None = None,
) -> float:
    """Expected profit of the trade.

    EV = P(converge) × reward × position − P(¬converge) × risk × position
    """
    if position_usd <= 0 or spread <= 0:
        return 0.0

    reward = max(reward_per_dollar if reward_per_dollar is not None else spread, 0.0)
    risk = max(risk_per_dollar if risk_per_dollar is not None else 0.5 * spread, 0.0)
    fee_estimate = 0.02

    win = convergence_prob * max(reward - fee_estimate, 0.0) * position_usd
    loss = (1 - convergence_prob) * risk * position_usd
    return round(win - loss, 4)
