import { useCallback, useEffect, useRef, useState } from 'react';
import type { ArbitrageSignal, SignalsStats } from '../lib/types';
import { api } from '../lib/api';
import StatsBar, { type SignalsRankingMode } from '../components/signals/StatsBar';
import SignalList from '../components/signals/SignalList';
import SignalDetail from '../components/signals/SignalDetail';

export default function SignalsPage() {
  const [signals, setSignals] = useState<ArbitrageSignal[]>([]);
  const [stats, setStats] = useState<SignalsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [ranking, setRanking] = useState<SignalsRankingMode>('profit');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchSignals = useCallback(async () => {
    try {
      const [data, s] = await Promise.all([
        api.getSignals(0, 0, 200, ranking),
        api.getSignalsStats(),
      ]);
      setSignals(data);
      setStats(s);
      setError(null);
      setSelectedId((prev) => {
        if (prev && data.some((c) => c.pair_id === prev)) return prev;
        return data[0]?.pair_id ?? null;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [ranking]);

  useEffect(() => {
    setLoading(true);
    fetchSignals();
  }, [fetchSignals]);

  useEffect(() => {
    intervalRef.current = setInterval(fetchSignals, 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchSignals]);

  const selectedSignal = signals.find((s) => s.pair_id === selectedId) ?? null;

  return (
    <div className="flex flex-col h-full">
      <StatsBar
        stats={stats}
        loading={loading}
        ranking={ranking}
        onRankingChange={setRanking}
      />
      <div className="flex flex-1 overflow-hidden">
        <SignalList
          signals={signals}
          loading={loading}
          error={error}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        <SignalDetail signal={loading ? null : selectedSignal} />
      </div>
    </div>
  );
}
