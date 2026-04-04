"""Tests for the simulation environment."""

from datetime import datetime, timezone

import pytest

from simulation.config import SimulationConfig
from simulation.data.loader import load_toy_dataset
from simulation.data.replay_stream import ReplayStream
from simulation.environment.env import SimulationEnvironment
from simulation.environment.clock import SimClock
from simulation.environment.state import StateManager
from simulation.models import EventType, MarketStatus


def _make_env(events=None) -> SimulationEnvironment:
    if events is None:
        events = load_toy_dataset()
    config = SimulationConfig(initial_capital=10_000)
    stream = ReplayStream(events)
    env = SimulationEnvironment(config=config, replay_stream=stream)
    env.reset()
    return env


class TestSimClock:
    def test_initial_time_advances(self) -> None:
        clock = SimClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
        clock.tick(datetime(2024, 1, 2, tzinfo=timezone.utc))
        assert clock.now.day == 2

    def test_backwards_tick_raises(self) -> None:
        clock = SimClock(datetime(2024, 6, 1, tzinfo=timezone.utc))
        with pytest.raises(ValueError):
            clock.tick(datetime(2024, 1, 1, tzinfo=timezone.utc))

    def test_same_time_tick_is_ok(self) -> None:
        t = datetime(2024, 1, 1, tzinfo=timezone.utc)
        clock = SimClock(t)
        clock.tick(t)  # should not raise


class TestStateManager:
    def test_market_created_appears_in_state(self) -> None:
        events = load_toy_dataset()
        manager = StateManager()
        for ev in events:
            if ev.event_type == EventType.MARKET_CREATED:
                manager.apply_event(ev)
                break

        assert len(manager.all_states()) > 0

    def test_market_resolved_changes_status(self) -> None:
        events = load_toy_dataset()
        manager = StateManager()
        for ev in events:
            manager.apply_event(ev)

        resolved = [s for s in manager.all_states().values()
                    if s.status == MarketStatus.RESOLVED]
        assert len(resolved) > 0

    def test_resolution_outcome_stored(self) -> None:
        events = load_toy_dataset()
        manager = StateManager()
        for ev in events:
            manager.apply_event(ev)

        for state in manager.all_states().values():
            if state.status == MarketStatus.RESOLVED:
                assert state.resolution_outcome is not None
                assert state.resolution_value is not None


class TestSimulationEnvironment:
    def test_reset_clears_state(self) -> None:
        env = _make_env()
        while not env.is_done():
            env.advance()
        env.reset()
        obs = env.get_observation()
        assert len(obs.visible_markets) == 0

    def test_advance_returns_event_count(self) -> None:
        env = _make_env()
        count = env.advance()
        assert count >= 0

    def test_done_after_all_events(self) -> None:
        env = _make_env()
        for _ in range(1000):
            if env.is_done():
                break
            env.advance()
        assert env.is_done()

    def test_observation_has_no_future_markets(self) -> None:
        """Markets created in the future must not appear in observations."""
        events = load_toy_dataset()
        # Advance only to first event
        config = SimulationConfig()
        stream = ReplayStream(events)
        env = SimulationEnvironment(config=config, replay_stream=stream)
        env.reset()
        env.advance()  # process first event only
        obs = env.get_observation()
        # Every market snapshot in observation must have snapshot_time <= sim_time
        for snap in obs.visible_markets.values():
            assert snap.snapshot_time <= obs.sim_time

    def test_observation_portfolio_initial_state(self) -> None:
        env = _make_env()
        env.advance()
        obs = env.get_observation()
        assert obs.portfolio.cash == 10_000
        assert obs.portfolio.realized_pnl == 0.0

    def test_finalize_returns_backtest_result(self) -> None:
        env = _make_env()
        while not env.is_done():
            env.advance()
        result = env.finalize()
        assert result.events_processed > 0
        assert result.metrics is not None
