export interface CandidatePair {
  id: string;
  question_id_a: string;
  question_id_b: string;
  text_a: string;
  text_b: string;
  market_a: string;
  market_b: string;
  price_a: number;
  price_b: number;
  price_spread: number;
  similarity_score: number;
  has_potential_negation: boolean;
  negation_tokens: string[];
  created_at: string;
}

export interface QuestionResponse {
  id: string;
  text: string;
  market: string;
  price: number;
}

export type StepStatus = 'done' | 'active' | 'pending' | 'error';

export interface PipelineStep {
  number: number;
  short_label: string;
  full_label: string;
  status: StepStatus;
  elapsed_ms: number | null;
  message: string | null;
}

export interface PipelineStatus {
  last_run: string | null;
  total_runtime_ms: number;
  steps: PipelineStep[];
  logs: string[];
}

export type RealismMode = 'optimistic' | 'realistic' | 'pessimistic';

export interface SimSummary {
  start_time: string;
  end_time: string;
  run_duration_s: number;
  events_processed: number;
  realized_pnl: number;
  unrealized_pnl: number;
  fees_paid: number;
  slippage_cost: number;
  final_equity: number;
  trades_attempted: number;
  trades_filled: number;
  partial_fills: number;
  fill_rate: number;
  win_rate: number;
  avg_profit_per_trade: number;
  avg_holding_hours: number;
  max_locked_capital: number;
  sharpe_ratio: number | null;
  max_drawdown: number;
  profit_by_arb_type: Record<string, number>;
  open_baskets: number;
  closed_baskets: number;
}

export interface EquityPoint {
  t: string;
  equity: number;
}

export interface TradeEntry {
  market_id: string;
  platform: string;
  side: string;
  price: number;
  size: number;
  status: string;
  fee: number;
  timestamp: string | null;
}

export interface SimResult {
  summary: SimSummary;
  equity_curve: EquityPoint[];
  trade_log: TradeEntry[];
  realism_mode: RealismMode;
}

export interface ArbitrageSignal {
  pair_id: string;
  platform_a: string;
  platform_b: string;
  market_a_id: string;
  market_b_id: string;
  text_a: string;
  text_b: string;
  price_a: number;
  price_b: number;
  raw_spread: number;
  direction: string;
  expected_profit: number;
  kelly_fraction: number;
  recommended_size_usd: number;
  confidence: number;
  regression_convergence_prob: number;
  created_at: string;
}

export interface SignalsStats {
  total: number;
  total_ev: number;
  top_ev: number;
  avg_confidence: number;
  avg_spread: number;
}

export interface SimTrade {
  pair_id: string;
  platform_a: string;
  platform_b: string;
  market_a_id: string;
  market_b_id: string;
  text_a: string;
  text_b: string;
  price_a: number;
  price_b: number;
  raw_spread: number;
  direction: string;
  expected_profit: number;
  recommended_size_usd: number;
  confidence: number;
  entry_date: string;
  exit_date: string;
  end_date_a: string | null;
  end_date_b: string | null;
  resolution_a: string | null;
  resolution_b: string | null;
  outcome: 'WIN' | 'LOSS' | 'UNKNOWN';
  realized_pnl: number | null;
}

export interface PnlPoint {
  date: string;
  daily_pnl: number;
  cumulative_pnl: number;
}

export interface AppConfig {
  embedding_model: string;
  similarity_threshold: number;
  db_status: 'connected' | 'disconnected' | 'error';
  markets: string[];
  last_run: string | null;
}
