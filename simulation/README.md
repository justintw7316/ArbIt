# ArbIt Simulation

Historical replay and backtesting environment for prediction market arbitrage strategies.

## Purpose

The simulator replays historical market data as if you were operating live in the past. It answers:

- What trades would the strategy have made?
- Would those trades have filled, and at what prices?
- How much profit would have been realized after fees and slippage?
- How much capital was tied up?
- How sensitive are results to execution assumptions?

This is **paper trading only** — no real money, no live connections.

---

## Architecture

```
HistoricalData (JSON/CSV/JSONL)
    │
    ▼
data/loader.py       — loads + normalizes raw records
data/replay_stream.py — time-orders events, deduplicates
data/adapters.py     — per-source format adapters
    │
    ▼
environment/env.py   — main orchestration loop
  ├─ environment/clock.py       — monotonic sim clock
  ├─ environment/state.py       — market state per event
  └─ environment/observation.py — builds strategy-visible snapshot
    │
    ├─ strategy/interface.py    ← strategy.decide(obs) → [TradeAction]
    │
    ▼
execution/fill_engine.py  — simulates fills
  ├─ execution/fees.py        — fee model
  ├─ execution/slippage.py    — slippage model (by realism mode)
  ├─ execution/baskets.py     — basket lifecycle tracking
  └─ execution/settlement.py  — payout on market resolution
    │
    ▼
portfolio/account.py    — cash, locked capital, positions
  ├─ portfolio/positions.py   — position registry
  ├─ portfolio/baskets.py     — basket analytics helpers
  └─ portfolio/settlement.py  — settlement helpers
    │
    ▼
analytics/
  ├─ metrics.py  — compute BacktestMetrics
  ├─ reports.py  — print/JSON summaries
  └─ charts.py   — chart-ready data (no matplotlib dep)
    │
    ▼
run_backtest.py  — orchestrates the full loop
```

---

## Plugging In a Strategy

Implement `BaseStrategy`:

```python
from simulation.strategy.interface import BaseStrategy
from simulation.models import Observation, TradeAction

class MyArbStrategy(BaseStrategy):
    def decide(self, observation: Observation) -> list[TradeAction]:
        actions = []
        for opp in observation.opportunities:
            if opp["net_profit_estimate"] > 0.02:
                # Build TradeAction with legs...
                actions.append(...)
        return actions
```

The strategy receives an `Observation` containing:
- `visible_markets`: all active market snapshots at current sim time
- `opportunities`: pre-detected arb opportunities (lightweight screen)
- `portfolio`: current cash, positions, open/closed baskets
- `recent_fills`: fills from the previous step
- `recent_settlements`: settlements from the previous step

---

## Loading Historical Data

**From files** (JSON, JSONL, or CSV):
```python
from simulation.data.loader import HistoricalDataLoader
loader = HistoricalDataLoader("path/to/data/")
events = list(loader.load())
```

**From raw dicts** (inline / tests):
```python
loader = HistoricalDataLoader("")
events = list(loader.load_from_records(my_records, adapter_source="generic"))
```

**Built-in toy dataset** (Bitcoin price arb scenario):
```python
from simulation.data.loader import load_toy_dataset
events = load_toy_dataset()
```

### Data format (generic JSON adapter)

```json
{
  "event_type": "market_updated",
  "platform": "polymarket",
  "market_id": "abc123",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "question": "Will X happen?",
    "outcomes": ["Yes", "No"],
    "best_bid":    {"Yes": 0.44, "No": 0.54},
    "best_ask":    {"Yes": 0.46, "No": 0.56},
    "last_traded": {"Yes": 0.45, "No": 0.55},
    "fees": 0.02,
    "close_time": "2024-12-31T00:00:00Z"
  }
}
```

Resolution events:
```json
{
  "event_type": "market_resolved",
  "platform": "polymarket",
  "market_id": "abc123",
  "timestamp": "2025-01-01T00:00:00Z",
  "data": { "resolution_outcome": "Yes", "resolution_value": 1.0 }
}
```

---

## Running a Backtest

```python
from simulation.run_backtest import run_backtest
from simulation.config import SimulationConfig
from simulation.models import RealismMode
from simulation.strategy.wrappers import GreedyArbStrategy

config = SimulationConfig(
    initial_capital=10_000,
    realism_mode=RealismMode.REALISTIC,
    min_profit_threshold=0.01,
)
result = run_backtest(config=config, strategy=GreedyArbStrategy())
```

Or as a script (uses toy dataset):
```bash
poetry run python -m simulation.run_backtest
```

---

## Realism Modes

| Mode | Fees (bps) | Slippage | Latency | Fill Probability |
|---|---|---|---|---|
| `OPTIMISTIC` | 50 | 0 | 0ms | 100% |
| `REALISTIC` | 100 | 50bps | 200ms | 85% |
| `PESSIMISTIC` | 200 | 150bps | 500ms | 65% |

Modes can be overridden per-param:
```python
config = SimulationConfig(
    realism_mode=RealismMode.REALISTIC,
    fee_bps=75.0,      # override fee only
)
```

---

## Running Tests

```bash
poetry run pytest simulation/tests/ -v
```
