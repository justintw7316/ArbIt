# ARBX Frontend Design Spec
**Date:** 2026-03-28
**Stack:** Next.js 14 (App Router) · Tailwind CSS · FastAPI backend · MongoDB
**Aesthetic:** Bloomberg Terminal — Orange Fire palette

---

## 1. Overview

ARBX is a live arbitrage signal board for prediction markets. It detects semantically similar questions priced differently across Polymarket, Kalshi, and Manifold, and surfaces them as tradeable candidates. The frontend presents these signals in a dense, data-first terminal UI — not a dashboard, not a SaaS product page. Every pixel is data.

**Three screens, one tab bar:**
| Tab | Purpose |
|-----|---------|
| SIGNALS | Primary screen — live arbitrage candidate list + detail panel |
| MARKETS | Per-market question feed with counts |
| PIPELINE | 7-step processing status grid |

---

## 2. Visual Design System

### Palette — Orange Fire
```
Background:     #060810   (near-black navy)
Surface:        #0d1117   (elevated cards, panels)
Border:         #1a2040   (panel dividers)
Orange (primary accent):  #ff6b35  (scores, active states, highlights)
Cyan (Polymarket):        #4fc3f7
Amber (Kalshi):           #ff9800
Purple (Manifold):        #a78bfa
Green (live / positive):  #00e676
Red (negation / warning): #ff3b3b
Text primary:   #ffffff
Text secondary: #94a3b8
Text muted:     #4a5568
```

### Typography
- **Font:** `'Courier New', monospace` — terminal feel throughout
- **All labels:** letter-spacing 1–3px, uppercase
- **Numbers / scores:** larger weight, orange tint
- **Question text:** normal weight, white, sentence case

### Motion
- Signal list rows: fade-in on data refresh (200ms opacity transition)
- Detail panel: cross-fade when selection changes (150ms)
- Stats bar numbers: count-up animation on first load
- Live indicator: slow pulse on `● LIVE` dot
- No page transitions — instant tab switches, content fades in

---

## 3. Layout — Global Shell

```
┌─────────────────────────────────────────────────────────────┐
│  ARBX  [SIGNALS] [MARKETS] [PIPELINE]          ● LIVE  17▸  │  ← Tab bar (48px)
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                   <screen content>                          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  MODEL: all-mpnet-base-v2  THRESHOLD: 0.70  DB: CONNECTED  │  ← Status bar (28px)
└─────────────────────────────────────────────────────────────┘
```

**Tab bar:** `ARBX` wordmark (orange, bold, tracked) on the left. Three tabs — active tab has bottom border in orange (`border-b-2 border-[#ff6b35]`) and white text; inactive tabs are muted. `● LIVE` pulse + total candidate count (derived from `/api/candidates` response length) on the right.

**Status bar:** Fixed bottom strip. Populated from `GET /api/config`. Shows: embedding model name, similarity threshold, MongoDB connection state. Muted text, monospace, 11px. If `/api/config` fails, shows `DB: ERROR` in red and dashes for other fields.

---

## 4. Screen 1 — SIGNALS (Primary)

### Stats Bar (below tab bar)
Six inline stat blocks separated by vertical dividers, all derived client-side from the `CandidatePair[]` array — no additional API call:
- `17 CANDIDATES` — `candidates.length` (orange)
- `9 HIGH CONF ≥0.90` — count where `similarity_score >= 0.90` (green)
- `2 NEGATION ▲` — count where `has_potential_negation === true` (red)
- `0.953 TOP SCORE` — `Math.max(...candidates.map(c => c.similarity_score))` (orange)
- `78pp BEST SPREAD` — `Math.max(...candidates.map(c => c.price_spread)) * 100` formatted as `Xpp` (green)
- `14:32:07 LAST RUN` — `last_run` from `/api/config`, formatted client-side as local `HH:MM:SS` (muted)

**Loading state:** Each stat block shows a `--` placeholder while data is in flight.
**Empty state (zero candidates):** All blocks show `0` / `--` with muted styling. No error shown.

### Split Panel
```
┌────────────────────┬────────────────────────────────────────┐
│  RANKED BY SIM ▾   │  SIGNAL DETAIL                         │
│  [ALL] [≥.90] [NEG]│                                        │
│                    │  ┌──────────────────┐  ┌────────────┐  │
│  0.95 POLY→KALSHI  │  │ ◆ POLYMARKET     │  │ ◆ KALSHI   │  │
│  US recession...   │  │ p=0.33           │  │ p=0.30     │  │
│  +3pp spread  ──── │  │ Will the US...   │  │ US reces.. │  │
│                    │  └──────────────────┘  └────────────┘  │
│  ⚠ 0.95 POLY→KALS  │                                        │
│  Fed NOT raise...  │  SIM SCORE    PRICE SPREAD   VOLUME    │
│  +78pp spread ──── │  0.953        +3pp           --        │
│                    │                                        │
│  0.95 POLY→MANIF   │  LLM STATUS: PENDING                   │
│  Bitcoin $150k...  │                                        │
└────────────────────┴────────────────────────────────────────┘
```

**Initial state:** First row is auto-selected on load. The detail panel always shows the selected signal — it is never blank.

**Left panel — Signal List:**
- Each row: similarity score (orange, bold) · market badges (`POLY`, `KALS`, `MANIF` colored pills) · question text snippet from `text_a` (truncated to 1 line with CSS `truncate`) · spread below as `+Xpp` in smaller text (`price_spread * 100` rounded to integer)
- Negation rows: left border red, `⚠ NEGATION` badge in red, dark red background tint
- Normal rows: left border transparent at rest, orange on hover, full orange when selected
- Selected row: full orange left border, slightly elevated background (`#0d1117`)
- Filter buttons: `ALL` / `≥.90` / `NEG` — pill toggles, orange when active. Filtering is client-side.

**Selection persistence on re-fetch:** When the 30s polling re-fetch completes, the currently selected row stays selected (matched by `id`). If the previously selected `id` no longer exists in the refreshed list (e.g., score dropped below `min_score`), selection resets to the first item in the updated list. No flash or scroll jump — diff is applied in-place.

**Loading state (first fetch):** List area shows 6 skeleton rows — same height as real rows, background `#0d1117`, animated `opacity-pulse`. Detail panel shows skeleton too.

**Empty state per filter:**
- `ALL` with zero candidates: message "NO SIGNALS — pipeline has not run yet" in muted text, centered.
- `≥.90` with zero results: "NO HIGH-CONFIDENCE SIGNALS"
- `NEG` with zero results: "NO NEGATION CANDIDATES"

**Error state:** If `/api/candidates` returns non-200: list area shows `⚠ FETCH ERROR — [status code]` in red. Retry button triggers re-fetch.

**Right panel — Signal Detail:**
- Two side-by-side market cards showing: platform name (colored), full question text (`text_a` / `text_b`), probability as large number (`price_a` / `price_b` × 100 + `%`)
- Below cards: 4 stat blocks — SIM SCORE (`similarity_score`), PRICE SPREAD (`price_spread * 100` as `+Xpp`), VOLUME (shown as `--` — not in data model, reserved slot), LLM STATUS (shown as `PENDING` — not in data model at this step, reserved slot)
- If `has_potential_negation`: full-width red banner "⚠ POTENTIAL NEGATION — these questions may be inverses. Tokens: `[negation_tokens.join(', ')]`"

---

## 5. Screen 2 — MARKETS

Three equal-width columns, one per market (Polymarket cyan, Kalshi amber, Manifold purple).
Data source: `GET /api/questions` called three times in parallel with `?market=polymarket`, `?market=kalshi`, `?market=manifold`.

Each column:
```
┌──────────────────────────────┐
│ ◆ POLYMARKET                 │
│ 3,241 LIVE MARKETS  8 FOUND  │
├──────────────────────────────┤
│ Will BTC exceed $150k...     │
│ p = 0.41                     │
│ ─────────────────────────── │
│ Will the US enter reces...   │
│ p = 0.33                     │
│ ─────────────────────────── │
│ Will Fed NOT raise rates?    │
│ p = 0.12                     │
└──────────────────────────────┘
```

- Header: colored dot + market name + total question count (from `questions.length`) + candidates-found count (cross-referenced from the `candidates` array already in memory from Screen 1, or passed via shared state at the layout level)
- Question list: scrollable, each entry shows `text` + `price` formatted as `p = X.XX`
- Questions whose `id` appears as `question_id_a` or `question_id_b` in any candidate pair are marked with an orange `◆` dot

**Loading state:** Three columns each show 5 skeleton rows while fetching.
**Empty state:** If a market returns 0 questions: "NO QUESTIONS SCRAPED YET" in muted text.
**Error state:** Column shows `⚠ LOAD FAILED` in red within that column only. Other columns render normally.

---

## 6. Screen 3 — PIPELINE

Seven-step status grid. Data source: `GET /api/pipeline-status`.

```
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│  ✓   │→│  ✓   │→│  ●   │→│  ○   │→│  ○   │→│  ○   │→│  ○   │
│  01  │ │  02  │ │  03  │ │  04  │ │  05  │ │  06  │ │  07  │
│SCRAPE│ │VECTOR│ │ LLM  │ │ ARB  │ │TIMING│ │  SIM │ │ DISP │
│      │ │  DB  │ │VERIFY│ │ CALC │ │      │ │      │ │      │
│ DONE │ │ DONE │ │ACTIVE│ │PEND  │ │PEND  │ │PEND  │ │PEND  │
│ 2.1s │ │ 4.3s │ │  --  │ │  --  │ │  --  │ │  --  │ │  --  │
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```

**Canonical step labels (short / full):**
| # | Short | Full |
|---|-------|------|
| 01 | SCRAPE | Market Scraper |
| 02 | VECTOR DB | Embedding & Vector DB |
| 03 | LLM VERIFY | LLM Verifier |
| 04 | ARB CALC | Arbitrage Calculator |
| 05 | TIMING | Timing Localizer |
| 06 | SIM | Simulator |
| 07 | DISP | Display |

**Step card states:**
- **done:** green checkmark `✓`, green border `#00e676`, elapsed_ms formatted as `X.Xs`
- **active:** orange pulsing dot `●`, orange border `#ff6b35`, spinner animation, no time shown
- **pending:** muted hollow circle `○`, muted border `#1a2040`, `--` for time
- **error:** red `✗`, red border `#ff3b3b`, error message truncated to 1 line

Below the grid: a log console showing the last 20 lines from `logs` (see Step schema). Green text on `#040608` background — real terminal look.

**Loading state:** Seven skeleton cards, muted.
**Empty state (pipeline never run):** All cards show `pending`. Log console shows "PIPELINE HAS NOT RUN".
**Error state (fetch fails):** Grid area shows `⚠ CANNOT REACH PIPELINE STATUS ENDPOINT` in red.

---

## 7. API Contracts

FastAPI backend — all responses JSON, no auth, CORS `*` for local dev (`localhost:3000`).

### `GET /api/candidates`
**Query params:**
- `min_score` (optional float, default `0.70`) — minimum similarity score
- `limit` (optional int, default `200`) — max results

**Response 200** — always returns an array, empty array `[]` if collection is empty or pipeline has never run (never 404):
```json
[
  {
    "id": "abc123",
    "question_id_a": "poly_q_001",
    "question_id_b": "kalshi_q_007",
    "text_a": "Will the US enter a recession in 2025?",
    "text_b": "US recession by end of 2025?",
    "market_a": "polymarket",
    "market_b": "kalshi",
    "price_a": 0.33,
    "price_b": 0.30,
    "price_spread": 0.03,
    "similarity_score": 0.953,
    "has_potential_negation": false,
    "negation_tokens": [],
    "created_at": "2026-03-28T14:32:07Z"
  }
]
```

**Serialization note:** This flat shape is exactly what `vector_db/vector_db/mongo_adapter.py :: _pair_to_doc()` writes to MongoDB. The `CandidatePair` Python dataclass has nested `question_a` / `question_b` sub-objects, but the serializer denormalizes them: `text_a = question_a.text`, `price_a = question_a.price`, etc. `price_spread` = `round(abs(price_a - price_b), 4)` is computed at write time. FastAPI reads these documents directly from MongoDB and returns them as-is — no additional transformation needed.

**Response 500:** `{ "error": "string describing failure" }`

---

### `GET /api/questions`
**Query params:**
- `market` (optional string: `"polymarket"` | `"kalshi"` | `"manifold"`) — if omitted, returns all markets

**Response 200:**
```json
[
  {
    "id": "poly_q_001",
    "text": "Will the US enter a recession in 2025?",
    "market": "polymarket",
    "price": 0.33
  }
]
```

Note: `metadata` is stripped server-side — the frontend does not receive it. Only `id`, `text`, `market`, `price` are returned.

**Response 500:** `{ "error": "string" }`

---

### `GET /api/pipeline-status`
**Response 200** — always returns all 7 step objects. Steps that haven't run yet have `status: "pending"` and `elapsed_ms: null`. The frontend uses the `number` field to match cards to canonical labels (hardcoded on the client from the table in Section 6) — `short_label` and `full_label` are included in the response as a convenience but the frontend may use its own hardcoded labels for pending steps not yet reported by the backend.

```json
{
  "last_run": "2026-03-28T14:32:07Z",
  "total_runtime_ms": 12300,
  "steps": [
    {
      "number": 1,
      "short_label": "SCRAPE",
      "full_label": "Market Scraper",
      "status": "done",
      "elapsed_ms": 2100,
      "message": null
    },
    {
      "number": 2,
      "short_label": "VECTOR DB",
      "full_label": "Embedding & Vector DB",
      "status": "done",
      "elapsed_ms": 4300,
      "message": null
    },
    {
      "number": 3,
      "short_label": "LLM VERIFY",
      "full_label": "LLM Verifier",
      "status": "active",
      "elapsed_ms": null,
      "message": "Processing 17 candidates..."
    },
    {
      "number": 4,
      "short_label": "ARB CALC",
      "full_label": "Arbitrage Calculator",
      "status": "pending",
      "elapsed_ms": null,
      "message": null
    }
  ]
}
```

_(Steps 5–7 omitted from example for brevity; backend always returns all 7.)_

**`status` enum values:** `"done"` | `"active"` | `"pending"` | `"error"`
**`elapsed_ms`:** null when status is `active`, `pending`, or `error`
**`message`:** reused for both active progress text and error description. If `status === "error"`, `message` contains the error string. If `status === "active"`, `message` is a progress string. Otherwise null.
**`logs`:** last 20 log lines, newest last. Empty array `[]` if pipeline has never run.
**`last_run`:** ISO8601 UTC; frontend formats to local `HH:MM:SS` for Stats Bar display. Null if pipeline has never run.

**Response 500:** `{ "error": "string" }`

---

### `GET /api/config`
**No params.**

**Response 200:**
```json
{
  "embedding_model": "all-mpnet-base-v2",
  "similarity_threshold": 0.70,
  "db_status": "connected",
  "markets": ["polymarket", "kalshi", "manifold"],
  "last_run": "2026-03-28T14:32:07Z"
}
```

**`db_status` values:** `"connected"` | `"disconnected"` | `"error"`
**Response 500:** `{ "error": "string" }` — UI falls back to showing `--` for all fields and `DB: ERROR` in red.

---

## 8. Component Architecture (Next.js)

### Client vs Server boundary
All data-fetching components are **Client Components** (`"use client"`) to support 30s polling via `useEffect`. The only Server Component is `app/layout.tsx` (renders the shell HTML). All screen pages and data components are client-side.

```
app/
  layout.tsx            — Server Component: global shell HTML only (no data)
  page.tsx              — redirect to /signals
  signals/page.tsx      — "use client": fetches /api/candidates, /api/config; owns polling
  markets/page.tsx      — "use client": fetches /api/questions × 3 in parallel
  pipeline/page.tsx     — "use client": fetches /api/pipeline-status, polls every 10s

components/
  TabBar.tsx            — receives candidateCount prop, "use client" for live pulse
  StatusBar.tsx         — receives ConfigResponse prop
  signals/
    StatsBar.tsx        — pure component, derives all stats from CandidatePair[]
    SignalList.tsx       — "use client": owns selectedId state, renders SignalRow list
    SignalRow.tsx        — pure component
    SignalDetail.tsx     — pure component, receives selected CandidatePair
  markets/
    MarketColumn.tsx    — pure component, receives QuestionResponse[] + candidateIds set
    QuestionRow.tsx     — pure component
  pipeline/
    PipelineGrid.tsx    — pure component, receives PipelineStatus
    StepCard.tsx        — pure component
    PipelineLog.tsx     — pure component, receives logs string[]

lib/
  api.ts                — typed fetch wrappers; throws on non-200 with {status, message}
  types.ts              — CandidatePair, QuestionResponse, PipelineStatus, StepStatus, ConfigResponse
```

**Shared state:** `markets/page.tsx` independently fetches `/api/candidates` (same call, same data, small payload). It builds a `Set<string>` of `question_id_a` and `question_id_b` values locally to drive the `◆` marker on question rows. No cross-page state sharing — each page is self-contained.

---

## 9. Data Flow

```
MongoDB
  ↓ (FastAPI reads)
/api/candidates   /api/questions×3   /api/pipeline-status   /api/config
  ↓
Client Components fetch on mount
  ↓
Render with data
  ↓ (every 30s for signals, every 10s for pipeline)
Re-fetch → reconcile state → re-render changed rows only (React diffing)
```

No WebSockets. Polling is sufficient given pipeline runs every ~30s.

---

## 10. Constraints & Non-Goals

- **No mock data** — all numbers come from real MongoDB collections written by steps 1–6. Empty states (not error states) are shown when collections are empty.
- **No auth** — local/demo use only
- **No mobile layout** — designed for 1440px+ wide screens (terminal UIs are desktop-first)
- **No dark/light toggle** — always dark
- **No charting library** — no Recharts/Chart.js; probability displayed as numbers, not graphs
- **Tailwind only** — no CSS-in-JS, no styled-components
- **VOLUME field** in Signal Detail shown as `--` — not available in current data model; slot reserved for future step 4 output
- **LLM STATUS field** in Signal Detail shown as `PENDING` — not available at step 2; will be populated once step 3 (LLM verifier) writes back to the same candidate pair document
