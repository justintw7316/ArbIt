# Phase 3 — Validation & Adjudication

Phase 3 sits between Phase 2 (vector similarity search) and Phase 4 (arbitrage engine). It receives candidate market pairs and decides which are truly equivalent or dependency-linked events worth passing to Phase 4.

## Architecture

```
CandidatePair (from Phase 2)
    │
    ▼
Layer 1: Classifier      — regex template matching (MarketTemplate)
    │
    ▼
Layer 2: Extractor       — soft NLP feature extraction (entities, dates, thresholds)
    │
    ▼
Layer 3: Contradictions  — hard contradiction filter (high-confidence rejections only)
    │  └─ hard_reject? → REJECT (skip layers 4–6)
    ▼
Layer 4: Reranker        — weighted relevance score (0–1)
    │
    ▼
Layer 5: LLM Judge       — DeepSeek adjudication (final call)
    │
    ▼
Layer 6a: Mapping        — outcome label mapping
Layer 6b: Arb Filter     — arb basket compatibility check
    │
    ▼
Layer 7: Graph Builder   — event cluster consolidation
    │
    ▼
Phase3Decision (to Phase 4)
```

## Design Principles

- **Lenient validation**: Rules only reject on HIGH-confidence positive evidence of mismatch. Missing fields are always neutral.
- **LLM is the final judge**: The contradiction filter is a fast pre-filter, not the arbiter.
- **Dead letter queue**: Failed/errored candidates go to `REVIEW` verdict, never silently dropped.
- **Async first**: Batch processing uses `asyncio.gather` for parallel LLM calls.
- **No spaCy**: NLP done with regex + stdlib to keep the install simple.
- **OpenAI SDK for DeepSeek**: DeepSeek has an OpenAI-compatible API; no extra dependency needed.

## Contradiction Rules (Layer 3)

Hard rejection only when **all** of:
1. Different normalized primary entity (confidence > 0.85)
2. Clearly incompatible templates (binary vs exhaustive multi-outcome, both confidence > 0.8)
3. Date window gap > `PHASE3_DATE_TOLERANCE_DAYS` (default: 30 days)
4. Numeric threshold mismatch > 5% (when both markets have explicit thresholds)
5. Nomination-event vs general-election pattern mismatch

Missing data → NEUTRAL (never rejects).

## Configuration

Set via `.env` (see `.env.example` in project root):

| Variable | Default | Description |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | DeepSeek API key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API base URL |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Model name |
| `DEEPSEEK_TEMPERATURE` | `0.1` | Sampling temperature |
| `DEEPSEEK_MAX_RETRIES` | `3` | Retry count on failure |
| `PHASE3_DATE_TOLERANCE_DAYS` | `30` | Max date gap before rejection |
| `PHASE3_ENTITY_MATCH_THRESHOLD` | `0.85` | Entity mismatch confidence threshold |
| `PHASE3_LLM_RATE_LIMIT_RPS` | `5` | Token bucket rate limit (req/sec) |
| `PHASE3_ENABLE_CACHE` | `false` | Enable judgment caching hook |
| `PHASE3_RERANKER_TYPE` | `mock` | `mock` or `openai` |

## Running Tests

```bash
poetry run pytest algorithm/Phase_3/tests/ -v
```

## Smoke Test

```bash
poetry run python -m algorithm.Phase_3.engine
```

Runs a mock Bitcoin price pair through the full pipeline (requires `DEEPSEEK_API_KEY` for Layer 5, or will return `REVIEW` on LLM failure).

## Output: `Phase3Decision`

```python
class Phase3Decision:
    candidate_id: str
    verdict: Verdict               # ACCEPT | REJECT | REVIEW
    reason: str
    contradiction_flags: list[str]
    extracted_features_a/b: ExtractedFeatures
    template_labels: list[TemplateResult]
    reranker_score: float
    llm_verdict: LLMJudgment
    relationship_type: RelationshipType
    outcome_mapping: OutcomeMappingResult
    arb_compatibility: ArbCompatibilityResult
    confidence: float              # calibrated 0–1; usable by Phase 4 for position sizing
    processing_time_ms: float
    error: str | None              # set on dead-letter candidates
```
