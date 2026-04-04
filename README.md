# ArbIt — Guaranteed Arbitrage Engine for Prediction Markets

A production-style quantitative system for detecting and simulating **risk-free arbitrage** across prediction market platforms (Polymarket, Kalshi, Manifold, and others).

> This is NOT a forecasting system. No probabilistic models. No predictions. Pure math.

---

## What It Does

Prediction markets on different platforms sometimes price the same real-world event differently. When the combined cost of buying all outcomes across platforms is less than the guaranteed payout, a **risk-free profit** exists.

This system:
1. Ingests markets from multiple platforms continuously
2. Identifies candidate matches using vector similarity search
3. Validates matches strictly (same event, same resolution, same timing)
4. Constructs arbitrage baskets and computes guaranteed profit after fees, slippage, and liquidity constraints
5. Simulates historical execution to produce a realistic PnL curve

---

## Arbitrage Condition

```
sum(cost_per_leg) < guaranteed_payout

where:
  cost_per_leg = price + fees + slippage
  guaranteed_payout = 1.00 (binary markets resolve to $1)
```

If this condition holds across a validated market group, a guaranteed profit exists regardless of how the event resolves.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      PIPELINE                           │
│                                                         │
│  Phase 1          Phase 2          Phase 3              │
│  ─────────        ──────────       ──────────────────   │
│  Data             Vector           Candidate            │
│  Ingestion   ──►  Embeddings  ──►  Validation           │
│                                         │               │
│                                         ▼               │
│                   Phase 5          Phase 4              │
│                   ──────────       ──────────────────   │
│                   Orchestration ◄─ Arbitrage            │
│                                    Engine               │
│                                         │               │
│                                         ▼               │
│                              Simulation / Backtest      │
│                                         │               │
│                                         ▼               │
│                                   App (Frontend)        │
└─────────────────────────────────────────────────────────┘
```

---

## Phase Breakdown

### Phase 1 — Data Ingestion (`algorithm/Phase_1/`)

**Goal:** Pull and normalize market data from prediction market APIs.

**Responsibilities:**
- Fetch markets, outcomes, prices, orderbooks, fees, and timestamps from each platform
- Normalize into a unified schema
- Store raw + cleaned records

**Inputs:** Platform APIs (Polymarket, Kalshi, Manifold, ...)
**Outputs:** Normalized market objects in a unified schema

**Supported Platforms:**
| Platform   | Type        | API Style  |
|------------|-------------|------------|
| Polymarket | Binary/CLOB | REST       |
| Kalshi     | Binary      | REST       |
| Manifold   | Binary/Multi| REST       |

**Unified Market Schema:**
```json
{
  "platform": "polymarket",
  "market_id": "...",
  "question": "Will X happen by Y?",
  "outcomes": ["YES", "NO"],
  "prices": { "YES": 0.62, "NO": 0.41 },
  "orderbook": { ... },
  "fees": 0.02,
  "open_time": "...",
  "close_time": "...",
  "resolution_rules": "...",
  "fetched_at": "..."
}
```

**Rules:**
- No matching or arbitrage logic in this phase
- All data stored with fetch timestamp for historical replay

---

### Phase 2 — Vector Embeddings (`algorithm/Phase_2/`)

**Goal:** Reduce the search space for equivalent markets using semantic similarity.

**Responsibilities:**
- Clean and preprocess market text (question + description)
- Generate embeddings for each market
- Store vectors in a vector database
- Run nearest-neighbor search to produce candidate pairs/groups

**Inputs:** Normalized market objects from Phase 1
**Outputs:** Candidate pairs/groups of semantically similar markets

**Important:**
- This phase does NOT confirm equivalence — it only retrieves candidates
- Embedding model: `text-embedding-3-small` (OpenAI) or `all-MiniLM-L6-v2` (local)
- Vector store: Pinecone / pgvector / FAISS

---

### Phase 3 — Candidate Validation (`algorithm/Phase_3/`)

**Goal:** Determine whether candidate market pairs are truly equivalent — same event, same resolution, same outcome mapping.

**Responsibilities:**
- Validate: same underlying event
- Validate: same resolution criteria
- Validate: same time horizon / expiry
- Validate: correct outcome polarity mapping (YES↔YES or YES↔NO)
- Reject false positives from Phase 2

**Inputs:** Candidate pairs from Phase 2
**Outputs:** Validated market groups with outcome polarity mappings

**Validation Rules (all must pass):**
```
1. Event identity      — do they resolve on the same real-world event?
2. Resolution parity   — do they use the same resolution source/criteria?
3. Timing alignment    — do they expire within an acceptable window?
4. Outcome mapping     — is the polarity correctly assigned?
```

**Important:**
- This is the most critical correctness step in the entire system
- Must be deterministic and rule-based (no ML classifiers here)
- A false positive here leads to a fake arbitrage — catastrophic

---

### Phase 4 — Arbitrage Engine (`algorithm/Phase_4/`)

**Goal:** Construct arbitrage baskets, verify the arbitrage condition, size positions, and compute guaranteed profit.

**Responsibilities:**

1. **Build arbitrage baskets**
   - Cross-platform binary: buy YES on one platform, NO on another
   - Exhaustive multi-outcome sets

2. **Compute executable cost per leg**
   ```
   cost = best_ask_price + platform_fee + estimated_slippage
   ```

3. **Check arbitrage condition**
   ```
   sum(costs of all legs) < 1.00
   ```

4. **Size the position**
   - Constrained by orderbook depth at each leg
   - Constrained by available capital
   - Limited by the smallest executable leg (bottleneck)

5. **Compute output metrics**
   - Profit per unit = `1.00 - sum(costs)`
   - Max contracts = `min(depth across all legs)`
   - Total guaranteed profit = `profit_per_unit × max_contracts`

**Inputs:** Validated market groups from Phase 3
**Outputs:** Structured arbitrage opportunities with sizing and profit estimates

**Important:**
- No price prediction
- No probabilistic sizing
- Only math + execution constraints

---

### Phase 5 — Orchestration (`algorithm/Phase_5/`)

**Goal:** Handle real-world pipeline dynamics — new data, timing issues, partial fills, stale markets.

**Responsibilities:**
- Trigger re-embedding when new markets arrive
- Recompute validation and arbitrage incrementally (not full re-scan)
- Detect and handle stale/expired markets
- Handle partial fills and liquidity mismatches
- Deduplicate markets across platforms
- Ensure pipeline consistency end-to-end

**Edge Cases Handled:**
| Case                     | Handling Strategy                              |
|--------------------------|------------------------------------------------|
| New market arrives       | Embed → search candidates → validate → check arb |
| Market resolves/expires  | Remove from active set, archive                |
| Partial fill             | Re-size remaining legs, log slippage           |
| Liquidity mismatch       | Cap position at min-depth leg                  |
| Stale price data         | Flag, skip until refreshed                     |
| Duplicate markets        | Deduplicate by canonical ID                    |

---

### Simulation (`simulation/`)

**Goal:** Backtest the full pipeline over ~1 year of historical data with no hindsight bias.

**Responsibilities:**
- Replay market state at each historical timestep
- At each timestep: run Phase 2 → 3 → 4
- Simulate order execution with realistic fills
- Track capital deployed, trades executed, and PnL

**Simulation Rules:**
- Only use data available at that timestamp (no lookahead)
- Model fees, slippage, and depth as they were at execution time
- Track both winning and incomplete arbitrages (partial fills, etc.)

**Output Metrics:**
```
- Cumulative PnL over time
- Number of opportunities detected
- Win rate (all arbs should be 100% — if not, a bug exists)
- Capital efficiency (profit / capital deployed)
- Per-platform breakdown
- Trade log (every executed arb with full details)
```

---

### App — Frontend (`app/`)

**Goal:** Visualize system results in real time and historically.

**Views:**
- **Live Dashboard** — active arbitrage opportunities, sorted by profit
- **PnL Curve** — cumulative profit over simulation period
- **Trade Log** — every simulated/live trade with full breakdown
- **Opportunity Explorer** — browse all detected arbs by platform, size, profit

---

## Repository Structure

```
ArbIt/
├── algorithm/
│   ├── __init__.py
│   ├── Phase_1/        # Data ingestion
│   ├── Phase_2/        # Vector embeddings
│   ├── Phase_3/        # Candidate validation
│   ├── Phase_4/        # Arbitrage engine
│   └── Phase_5/        # Orchestration
├── simulation/         # Historical backtest
├── app/                # React + Vite frontend (npm)
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── data/               # Stored market data, snapshots
├── docs/               # Additional documentation
├── pyproject.toml      # Poetry — Python backend
├── poetry.lock
├── .gitignore
└── README.md
```

---

## Setup

### Prerequisites

| Tool   | Version  | Purpose                         |
|--------|----------|---------------------------------|
| Python | ^3.12    | Backend (algorithm, simulation) |
| Poetry | ^2.0     | Python dependency management    |
| Node   | ^20      | Frontend                        |
| npm    | ^10      | Frontend dependency management  |

---

### Backend (algorithm + simulation)

Uses **Poetry** for dependency management. All Python phases live in the `algorithm/` and `simulation/` packages.

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install all Python dependencies and create virtualenv
poetry install

# Activate the virtualenv
poetry env activate

# Run a script inside the virtualenv without activating
poetry run python algorithm/Phase_1/some_script.py
```

**Adding a new dependency:**
```bash
poetry add httpx          # runtime dependency
poetry add --group dev pytest  # dev-only dependency
```

> **Note:** `faiss-cpu` and `tiktoken` are excluded until Python 3.14 wheels are available.
> Alternatives for vector search: **pgvector** (Postgres extension) or **chromadb**.

---

### Frontend (app/)

Uses **React 19 + Vite + TypeScript**, managed with **npm**.

```bash
cd app

# Install dependencies
npm install

# Start development server (http://localhost:5173)
npm run dev

# Type-check + production build
npm run build

# Preview production build locally
npm run preview
```

**Adding a frontend dependency:**
```bash
cd app
npm install recharts       # runtime
npm install -D @types/foo  # dev/type-only
```

---

## Key Invariants

These must always hold throughout the system:

1. **No prediction** — the system never estimates probabilities or future prices
2. **Strict validation** — a market pair is only approved if ALL validation rules pass
3. **Cost-inclusive math** — all profit calculations include fees, slippage, and depth
4. **No hindsight** — simulation only uses data available at each timestep
5. **Phase separation** — no phase performs responsibilities belonging to another

---

## Guaranteed Arbitrage Types

### Type 1: Cross-Platform Binary
Same binary event, priced differently across two platforms.
```
Buy YES on Platform A at 0.48 + fees → cost: 0.50
Buy NO  on Platform B at 0.46 + fees → cost: 0.48
Total cost: 0.98 < 1.00 → Profit: $0.02 per contract
```

### Type 2: Exhaustive Multi-Outcome
All mutually exclusive outcomes across one or more platforms sum to less than $1.
```
Buy outcome A at 0.30
Buy outcome B at 0.25
Buy outcome C at 0.38
Total: 0.93 < 1.00 → Profit: $0.07 per contract
```

---

## Development Status

| Component       | Status                          |
|-----------------|---------------------------------|
| Phase 1         | Not started                     |
| Phase 2         | Not started                     |
| Phase 3         | Not started                     |
| Phase 4         | Not started                     |
| Phase 5         | Not started                     |
| Simulation      | Not started                     |
| App             | Scaffolded (React + Vite + TS)  |

---

## License

Private — not for public distribution.
