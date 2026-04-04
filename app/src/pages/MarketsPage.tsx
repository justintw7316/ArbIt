import { useEffect, useState } from 'react';
import type { CandidatePair, QuestionResponse } from '../lib/types';
import { api } from '../lib/api';
import MarketColumn from '../components/markets/MarketColumn';

const MARKETS = ['polymarket', 'kalshi', 'manifold'] as const;

interface MarketState {
  questions: QuestionResponse[];
  loading: boolean;
  error: string | null;
}

const DEFAULT_STATE: MarketState = { questions: [], loading: true, error: null };

export default function MarketsPage() {
  const [states, setStates] = useState<Record<string, MarketState>>({
    polymarket: { ...DEFAULT_STATE },
    kalshi: { ...DEFAULT_STATE },
    manifold: { ...DEFAULT_STATE },
  });
  const [pairIds, setPairIds] = useState<Set<string>>(new Set());
  const [candidateCounts, setCandidateCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    const fetches: [Promise<CandidatePair[]>, ...Promise<QuestionResponse[]>[]] = [
      api.getCandidates(),
      ...MARKETS.map((m) => api.getQuestions(m)),
    ];

    Promise.allSettled(fetches).then(([candidatesResult, ...marketResults]) => {
      if (candidatesResult.status === 'fulfilled') {
        const pairs = candidatesResult.value as CandidatePair[];
        const ids = new Set<string>();
        const counts: Record<string, number> = {};
        for (const p of pairs) {
          ids.add(p.question_id_a);
          ids.add(p.question_id_b);
          counts[p.market_a] = (counts[p.market_a] ?? 0) + 1;
          counts[p.market_b] = (counts[p.market_b] ?? 0) + 1;
        }
        setPairIds(ids);
        setCandidateCounts(counts);
      }

      setStates((prev) => {
        const next = { ...prev };
        MARKETS.forEach((market, i) => {
          const result = marketResults[i];
          if (result.status === 'fulfilled') {
            next[market] = { questions: result.value as QuestionResponse[], loading: false, error: null };
          } else {
            next[market] = { questions: [], loading: false, error: String(result.reason) };
          }
        });
        return next;
      });
    });
  }, []);

  return (
    <div className="flex h-full">
      {MARKETS.map((market) => (
        <MarketColumn
          key={market}
          market={market}
          questions={states[market].questions}
          pairIds={pairIds}
          candidateCount={candidateCounts[market] ?? 0}
          loading={states[market].loading}
          error={states[market].error}
        />
      ))}
    </div>
  );
}
