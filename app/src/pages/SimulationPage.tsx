import { useEffect, useRef, useState, useCallback } from 'react';
import type { SimTrade, PnlPoint } from '../lib/types';
import { api } from '../lib/api';

const MARKET_COLOR: Record<string, string> = {
  polymarket: '#4fc3f7',
  kalshi: '#ff9800',
  manifold: '#a78bfa',
};

const SPEEDS = [1, 5, 20, 100];

function PnlChart({ curve, currentDate }: { curve: PnlPoint[]; currentDate: string }) {
  if (curve.length === 0) return null;
  const allVals = curve.map((p) => p.cumulative_pnl);
  const max = Math.max(...allVals.map(Math.abs), 1);
  const w = 100 / (curve.length - 1 || 1);
  const currentIdx = curve.findIndex((p) => p.date >= currentDate);

  return (
    <div className="relative h-24 w-full border border-border bg-surface overflow-hidden">
      <span className="absolute top-1 left-2 text-[9px] text-text-muted tracking-widest z-10">CUMULATIVE P&L</span>
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 40" preserveAspectRatio="none">
        {/* zero line */}
        <line x1="0" y1="20" x2="100" y2="20" stroke="#333" strokeWidth="0.3" />
        {/* fill under curve */}
        {curve.length > 1 && (() => {
          const pts = curve.map((p, i) => `${i * w},${20 - (p.cumulative_pnl / max) * 18}`).join(' ');
          const lastX = (curve.length - 1) * w;
          const lastY = 20 - (curve[curve.length - 1].cumulative_pnl / max) * 18;
          const finalPnl = curve[curve.length - 1].cumulative_pnl;
          return (
            <polyline
              points={pts}
              fill="none"
              stroke={finalPnl >= 0 ? '#4ade80' : '#f87171'}
              strokeWidth="0.7"
              opacity="0.9"
            />
          );
        })()}
        {/* current date marker */}
        {currentIdx >= 0 && (
          <line
            x1={currentIdx * w} y1="0"
            x2={currentIdx * w} y2="40"
            stroke="#f97316" strokeWidth="0.6" strokeDasharray="2,1"
          />
        )}
      </svg>
      {/* current P&L label */}
      {currentIdx >= 0 && (
        <span
          className={`absolute bottom-1 right-2 text-[9px] font-bold tracking-wider ${
            (curve[currentIdx]?.cumulative_pnl ?? 0) >= 0 ? 'text-green' : 'text-red'
          }`}
        >
          {(curve[currentIdx]?.cumulative_pnl ?? 0) >= 0 ? '+' : ''}
          ${(curve[currentIdx]?.cumulative_pnl ?? 0).toFixed(2)}
        </span>
      )}
    </div>
  );
}

type TradeMode = 'entered' | 'open' | 'resolved';

function TradeCard({ trade, mode }: { trade: SimTrade; mode: TradeMode }) {
  const isWin = trade.outcome === 'WIN';
  const isLoss = trade.outcome === 'LOSS';

  const accentColor =
    mode === 'entered' ? '#f97316'
    : mode === 'resolved' ? (isWin ? '#4ade80' : isLoss ? '#f87171' : '#94a3b8')
    : '#64748b';

  const bgClass =
    mode === 'entered' ? 'bg-[#1a0e00]'
    : mode === 'resolved' ? (isWin ? 'bg-[#071a0a]' : isLoss ? 'bg-[#1a0707]' : 'bg-surface')
    : 'bg-surface';

  const label =
    mode === 'entered' ? '→ ENTER'
    : mode === 'resolved' ? (isWin ? '▲ WIN' : isLoss ? '▼ LOSS' : '◌ UNKN')
    : '◉ OPEN';

  const valueStr =
    mode === 'resolved' && trade.realized_pnl !== null
      ? `${trade.realized_pnl >= 0 ? '+' : ''}$${trade.realized_pnl.toFixed(2)}`
      : `EV $${trade.expected_profit.toFixed(2)}`;

  const metaStr =
    mode === 'entered'
      ? `expires ${trade.exit_date} · spread ${Math.round(trade.raw_spread * 10000)}bps · $${trade.recommended_size_usd.toFixed(0)}`
      : mode === 'resolved'
      ? `${trade.exit_date} · ${trade.resolution_a ?? '?'}/${trade.resolution_b ?? '?'} · spread ${Math.round(trade.raw_spread * 10000)}bps`
      : `closes ${trade.exit_date || '?'} · spread ${Math.round(trade.raw_spread * 10000)}bps · $${trade.recommended_size_usd.toFixed(0)}`;

  return (
    <div className={`px-3 py-2 border-b border-border ${bgClass} text-xs`}>
      <div className="flex items-center gap-2 mb-0.5">
        <span className="font-bold text-[10px] w-14 shrink-0" style={{ color: accentColor }}>
          {label}
        </span>
        <span
          className="text-[9px] font-bold px-1 border rounded shrink-0"
          style={{ color: MARKET_COLOR[trade.platform_a] ?? '#888', borderColor: MARKET_COLOR[trade.platform_a] ?? '#888' }}
        >
          {(trade.platform_a ?? '').toUpperCase().slice(0, 4)}
        </span>
        <span className="text-text-muted text-[9px]">↔</span>
        <span
          className="text-[9px] font-bold px-1 border rounded shrink-0"
          style={{ color: MARKET_COLOR[trade.platform_b] ?? '#888', borderColor: MARKET_COLOR[trade.platform_b] ?? '#888' }}
        >
          {(trade.platform_b ?? '').toUpperCase().slice(0, 4)}
        </span>
        <span className="ml-auto font-bold text-[10px] shrink-0" style={{ color: accentColor }}>
          {valueStr}
        </span>
      </div>
      <div className="text-text-primary truncate pl-16">{trade.text_a || trade.market_a_id}</div>
      <div className="text-text-muted text-[10px] mt-0.5 pl-16 truncate">{metaStr}</div>
    </div>
  );
}

export default function SimulationPage() {
  const [allTrades, setAllTrades] = useState<SimTrade[]>([]);
  const [pnlCurve, setPnlCurve] = useState<PnlPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selectedDate, setSelectedDate] = useState<string>('');

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    Promise.all([api.getSimulationTrades(), api.getSimulationPnlCurve()])
      .then(([trades, curve]) => {
        setAllTrades(trades);
        setPnlCurve(curve);
        setCurrentIdx(0);
        if (curve.length > 0) setSelectedDate(curve[0].date);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Continuous date array from the 365-day curve
  const dates = pnlCurve.map((p) => p.date);
  const totalDays = dates.length;
  const dayNum = currentIdx + 1;

  // Per-day trade buckets
  const enteredToday = allTrades.filter((t) => t.entry_date === selectedDate);
  const resolvedToday = allTrades.filter(
    (t) => t.exit_date === selectedDate && t.entry_date <= selectedDate,
  );
  const openPositions = allTrades.filter(
    (t) => t.entry_date <= selectedDate && (!t.exit_date || t.exit_date > selectedDate),
  );
  const resolvedSoFar = allTrades.filter(
    (t) => Boolean(t.exit_date) && t.exit_date <= selectedDate,
  );

  const wins = resolvedSoFar.filter((t) => t.outcome === 'WIN').length;
  const losses = resolvedSoFar.filter((t) => t.outcome === 'LOSS').length;
  const totalPnl = resolvedSoFar.reduce((s, t) => s + (t.realized_pnl ?? 0), 0);
  const curvePnl = pnlCurve[currentIdx]?.cumulative_pnl ?? 0;

  const tick = useCallback(() => {
    setCurrentIdx((prev) => {
      const next = prev + 1;
      if (next >= dates.length) {
        setPlaying(false);
        return prev;
      }
      setSelectedDate(dates[next]);
      return next;
    });
  }, [dates]);

  useEffect(() => {
    if (playing) {
      // Faster when there's no activity on the current day to skip quiet periods
      const hasActivity = enteredToday.length > 0 || resolvedToday.length > 0;
      const baseMs = Math.max(30, 500 / speed);
      const ms = hasActivity ? baseMs : Math.max(10, baseMs / 4);
      intervalRef.current = setInterval(tick, ms);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [playing, speed, tick, enteredToday.length, resolvedToday.length]);

  function handleReset() {
    setPlaying(false);
    setCurrentIdx(0);
    if (dates.length > 0) setSelectedDate(dates[0]);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-text-muted text-xs tracking-widest animate-pulse">LOADING SIMULATION...</span>
      </div>
    );
  }

  if (error) {
    return <div className="p-5 text-red text-xs tracking-wider">⚠ {error}</div>;
  }

  if (allTrades.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-text-muted text-xs tracking-widest">NO SIMULATION DATA — RUN THE PIPELINE FIRST</span>
      </div>
    );
  }

  const activityCount = enteredToday.length + resolvedToday.length;

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* Controls bar */}
      <div className="flex items-center gap-3 px-5 py-2 border-b border-border bg-surface shrink-0 flex-wrap">

        {/* Day counter */}
        <div className="flex flex-col shrink-0 w-20">
          <span className="text-[9px] text-text-muted tracking-[2px]">BACKTEST</span>
          <span className="text-[10px] text-text-secondary font-bold">
            DAY {dayNum}<span className="text-text-muted font-normal">/{totalDays}</span>
          </span>
        </div>

        <button
          onClick={() => setPlaying((p) => !p)}
          className={`px-3 py-1 text-xs tracking-widest border rounded transition-colors ${
            playing ? 'border-orange text-orange bg-orange/10' : 'border-green text-green hover:bg-green/10'
          }`}
        >
          {playing ? '⏸ PAUSE' : '▶ PLAY'}
        </button>

        <button
          onClick={handleReset}
          className="px-3 py-1 text-xs tracking-widest border border-border text-text-muted hover:text-text-secondary rounded"
        >
          ↺ RESET
        </button>

        <div className="flex items-center gap-1">
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className={`px-2 py-0.5 text-[10px] rounded border transition-colors ${
                speed === s ? 'border-orange text-orange' : 'border-border text-text-muted hover:text-text-secondary'
              }`}
            >
              {s}x
            </button>
          ))}
        </div>

        {/* Scrubber */}
        <div className="flex-1 min-w-32 flex items-center gap-2">
          <input
            type="range"
            min={0}
            max={Math.max(totalDays - 1, 0)}
            value={currentIdx}
            onChange={(e) => {
              const idx = Number(e.target.value);
              setCurrentIdx(idx);
              setSelectedDate(dates[idx] ?? '');
              setPlaying(false);
            }}
            className="flex-1 accent-orange cursor-pointer"
          />
          <span className="text-[10px] text-text-secondary tracking-wider w-24 shrink-0 text-right">
            {selectedDate || '--'}
          </span>
        </div>

        {/* Live stats */}
        <div className="flex gap-3 text-[10px] tracking-wider shrink-0">
          <span className="text-orange">◉ {openPositions.length} open</span>
          <span className="text-green">▲ {wins}W</span>
          <span className="text-red">▼ {losses}L</span>
          <span className={`font-bold ${totalPnl >= 0 ? 'text-green' : 'text-red'}`}>
            {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(0)} P&L
          </span>
        </div>
      </div>

      {/* P&L Chart */}
      <div className="px-5 pt-2 shrink-0">
        <PnlChart curve={pnlCurve} currentDate={selectedDate} />
      </div>

      {/* Main panels */}
      <div className="flex flex-1 overflow-hidden gap-3 px-5 pt-2 pb-3">

        {/* Left: today's activity */}
        <div className="flex flex-col border border-border shrink-0" style={{ width: '360px', minWidth: '260px' }}>
          <div className="px-3 py-2 border-b border-border shrink-0 flex items-center justify-between">
            <div>
              <span className="text-[10px] text-text-muted tracking-widest">
                {selectedDate || '--'}
              </span>
              {activityCount > 0 && (
                <span className="ml-2 text-[9px] text-orange tracking-widest">
                  {enteredToday.length > 0 && `+${enteredToday.length} entered`}
                  {enteredToday.length > 0 && resolvedToday.length > 0 && ' · '}
                  {resolvedToday.length > 0 && `${resolvedToday.length} resolved`}
                </span>
              )}
            </div>
            {activityCount === 0 && (
              <span className="text-[9px] text-text-muted tracking-widest">QUIET</span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto">
            {activityCount === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-1">
                <span className="text-text-muted text-[10px] tracking-widest">NO ACTIVITY</span>
                <span className="text-text-muted text-[9px]">{openPositions.length} positions open</span>
              </div>
            ) : (
              <>
                {enteredToday.map((t) => (
                  <TradeCard key={`e-${t.pair_id}`} trade={t} mode="entered" />
                ))}
                {resolvedToday.map((t) => (
                  <TradeCard key={`r-${t.pair_id}`} trade={t} mode="resolved" />
                ))}
              </>
            )}
          </div>
        </div>

        {/* Right: portfolio view */}
        <div className="flex flex-col flex-1 border border-border overflow-hidden">
          <div className="px-3 py-2 border-b border-border shrink-0 flex items-center justify-between">
            <span className="text-[10px] text-text-muted tracking-widest">
              PORTFOLIO · {openPositions.length} open · {resolvedSoFar.length} resolved
            </span>
            <span className={`text-xs font-bold ${curvePnl >= 0 ? 'text-green' : 'text-red'}`}>
              {curvePnl >= 0 ? '+' : ''}${curvePnl.toFixed(2)}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {/* Open positions first */}
            {openPositions.map((t) => (
              <TradeCard key={`o-${t.pair_id}`} trade={t} mode="open" />
            ))}
            {/* Resolved, newest first */}
            {[...resolvedSoFar].reverse().map((t) => (
              <TradeCard key={`rv-${t.pair_id}`} trade={t} mode="resolved" />
            ))}
            {openPositions.length === 0 && resolvedSoFar.length === 0 && (
              <div className="p-4 text-text-muted text-[10px] tracking-widest text-center">
                NO TRADES YET
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
