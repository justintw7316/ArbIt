"""
Backtest runner.

Orchestrates the full replay loop:
  1. Load historical data
  2. Build replay stream
  3. Initialize environment
  4. Initialize strategy
  5. Run event loop
  6. Finalize and produce BacktestResult
  7. Print/export analytics

Usage:
    from simulation.run_backtest import run_backtest
    from simulation.config import SimulationConfig
    from simulation.strategy.wrappers import GreedyArbStrategy

    config = SimulationConfig(initial_capital=10_000, realism_mode=RealismMode.REALISTIC)
    result = run_backtest(config=config, strategy=GreedyArbStrategy())
    print_summary(result)

Or as a script:
    poetry run python -m simulation.run_backtest
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from simulation.analytics.reports import print_summary, to_json
from simulation.config import SimulationConfig, default_config
from simulation.data.loader import HistoricalDataLoader, load_toy_dataset
from simulation.data.replay_stream import ReplayStream
from simulation.environment.env import SimulationEnvironment
from simulation.models import BacktestResult
from simulation.strategy.interface import BaseStrategy
from simulation.strategy.wrappers import GreedyArbStrategy, LoggingWrapper

logger = logging.getLogger(__name__)

# How often to sample the equity curve (every N steps)
_EQUITY_SAMPLE_INTERVAL = 10


def run_backtest(
    config: Optional[SimulationConfig] = None,
    strategy: Optional[BaseStrategy] = None,
    events=None,          # pre-loaded events (if None, loads from config.data_path)
    verbose: bool = True,
) -> BacktestResult:
    """
    Run a full backtest.

    Args:
        config:   simulation configuration (defaults to default_config())
        strategy: pluggable strategy (defaults to GreedyArbStrategy)
        events:   pre-loaded list of HistoricalReplayEvents (optional)
        verbose:  print summary on completion

    Returns:
        BacktestResult with metrics, trade log, and final portfolio state.
    """
    if config is None:
        config = default_config()

    if strategy is None:
        strategy = LoggingWrapper(GreedyArbStrategy())

    # ------------------------------------------------------------------
    # 1. Load historical data
    # ------------------------------------------------------------------
    if events is None:
        loader = HistoricalDataLoader(config.data_path)
        events = list(loader.load())
        if not events:
            logger.warning(
                "No events found at %s — using built-in toy dataset",
                config.data_path,
            )
            events = load_toy_dataset()

    logger.info("Loaded %d historical events", len(events))

    # ------------------------------------------------------------------
    # 2. Build replay stream
    # ------------------------------------------------------------------
    stream = ReplayStream(
        events=events,
        start_time=config.start_time,
        end_time=config.end_time,
        deduplicate=True,
    )
    first_ts, last_ts = stream.time_bounds()
    logger.info(
        "Replay window: %s → %s (%d events)",
        first_ts, last_ts, len(stream),
    )

    # ------------------------------------------------------------------
    # 3. Initialize environment
    # ------------------------------------------------------------------
    env = SimulationEnvironment(config=config, replay_stream=stream)
    env.reset()
    strategy.on_reset()

    # ------------------------------------------------------------------
    # 4. Run event loop
    # ------------------------------------------------------------------
    step = 0
    opportunities_seen = 0
    t0 = time.monotonic()

    while not env.is_done():
        # Get observation
        obs = env.get_observation()
        opportunities_seen += len(obs.opportunities)

        # Strategy decides
        actions = strategy.decide(obs)

        # Apply actions
        fills = env.apply_actions(actions)
        if fills:
            strategy.on_fill(fills)

        # Advance time
        env.advance()

        # Sample equity curve periodically
        if step % _EQUITY_SAMPLE_INTERVAL == 0:
            env._account.snapshot_equity(obs.sim_time)

        step += 1

    elapsed = time.monotonic() - t0
    logger.info(
        "Replay complete: %d steps, %.2fs wall time", step, elapsed
    )

    # ------------------------------------------------------------------
    # 5. Finalize
    # ------------------------------------------------------------------
    result = env.finalize()
    result.metrics.opportunities_detected = opportunities_seen

    # Attach equity curve samples from account
    result.metrics.equity_curve = env._account._equity_samples

    if verbose:
        print_summary(result)

    return result


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    result = run_backtest(verbose=True)
    print("\nJSON summary:")
    print(to_json(result))
