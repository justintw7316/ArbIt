import type { CandidatePair, QuestionResponse, PipelineStatus, AppConfig, SimResult, RealismMode, ArbitrageSignal, SignalsStats, SimTrade, PnlPoint } from './types';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { error?: string };
    throw new ApiError(res.status, body.error ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const b = await res.json().catch(() => ({})) as { detail?: { error?: string } };
    throw new ApiError(res.status, b.detail?.error ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getCandidates: (minScore = 0.70, limit = 200) =>
    get<CandidatePair[]>(`/api/candidates?min_score=${minScore}&limit=${limit}`),
  getSignals: (
    minEv = 0.0,
    minConfidence = 0.0,
    limit = 200,
    ranking: 'profit' | 'diverse' = 'profit',
  ) =>
    get<ArbitrageSignal[]>(
      `/api/signals?min_ev=${minEv}&min_confidence=${minConfidence}&limit=${limit}&ranking=${ranking}`,
    ),
  getSignalsStats: () =>
    get<SignalsStats>('/api/signals/stats'),
  getQuestions: (market?: string) =>
    get<QuestionResponse[]>(`/api/questions${market ? `?market=${market}` : ''}`),
  getPipelineStatus: () =>
    get<PipelineStatus>('/api/pipeline-status'),
  getSimulationTrades: () =>
    get<SimTrade[]>('/api/simulation/trades'),
  getSimulationPnlCurve: () =>
    get<PnlPoint[]>('/api/simulation/pnl-curve'),
  getConfig: () =>
    get<AppConfig>('/api/config'),
  runSimulation: (realism_mode: RealismMode, initial_capital: number) =>
    post<SimResult>('/api/simulation/run', { realism_mode, initial_capital }),
};
