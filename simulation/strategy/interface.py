"""
Strategy interface.

All arbitrage strategies must implement BaseStrategy. The environment calls
strategy.decide(observation) at each timestep and passes the returned
TradeActions to the fill engine.

The strategy receives only what is in the Observation object — it has no
direct access to the environment, clock, or market state manager.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from simulation.models import Observation, TradeAction


class BaseStrategy(ABC):
    """Abstract base class for all simulation strategies."""

    @abstractmethod
    def decide(self, observation: Observation) -> list[TradeAction]:
        """
        Inspect the observation and return zero or more trade actions.

        This method must:
          - Only use data from the observation (no external state)
          - Return immediately (no I/O, no blocking)
          - Be deterministic for reproducibility

        Args:
            observation: current environment observation (no future data)

        Returns:
            List of TradeActions to submit. May be empty.
        """
        ...

    def on_fill(self, fill_results: list) -> None:
        """Optional hook called after fills are processed."""

    def on_settlement(self, settlement_results: list) -> None:
        """Optional hook called after settlements are processed."""

    def on_reset(self) -> None:
        """Called when the environment resets."""


class StrategyProtocol(Protocol):
    """Duck-typed protocol for strategies that don't extend BaseStrategy."""

    def decide(self, observation: Observation) -> list[TradeAction]:
        ...
