import type { QuestionResponse } from '../../lib/types';
import QuestionRow from './QuestionRow';

const MARKET_COLOR: Record<string, string> = {
  polymarket: '#4fc3f7',
  kalshi: '#ff9800',
  manifold: '#a78bfa',
};
const MARKET_GLOW: Record<string, string> = {
  polymarket: '0 0 12px rgba(79,195,247,0.5)',
  kalshi: '0 0 12px rgba(255,152,0,0.5)',
  manifold: '0 0 12px rgba(167,139,250,0.5)',
};
const MARKET_LABEL: Record<string, string> = {
  polymarket: 'POLYMARKET',
  kalshi: 'KALSHI',
  manifold: 'MANIFOLD',
};

interface MarketColumnProps {
  market: string;
  questions: QuestionResponse[];
  pairIds: Set<string>;
  candidateCount: number;
  loading: boolean;
  error: string | null;
}

export default function MarketColumn({ market, questions, pairIds, candidateCount, loading, error }: MarketColumnProps) {
  const color = MARKET_COLOR[market] ?? '#94a3b8';
  const glow = MARKET_GLOW[market] ?? 'none';
  const label = MARKET_LABEL[market] ?? market.toUpperCase();

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      flex: 1,
      minWidth: 0,
      height: '100%',
      borderRight: '1px solid #0a0d1a',
    }}>
      {/* Column header */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid #0a0d1a',
        background: 'linear-gradient(180deg, #070a14 0%, #060810 100%)',
        flexShrink: 0,
        borderLeft: `3px solid ${color}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{
            fontSize: '9px',
            fontWeight: '600',
            color,
            letterSpacing: '0.25em',
            textShadow: glow,
          }}>
            ◆ {label}
          </span>
          {candidateCount > 0 && (
            <span style={{
              fontSize: '8px',
              color: '#ff6b35',
              letterSpacing: '0.15em',
              textShadow: '0 0 8px rgba(255,107,53,0.4)',
            }}>
              {candidateCount} ARBIT
            </span>
          )}
        </div>
        <span style={{ fontSize: '8px', color: '#2a3060', letterSpacing: '0.15em' }}>
          {loading ? '--' : questions.length.toLocaleString()} MARKETS
        </span>
      </div>

      {/* Rows */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} style={{ padding: '8px 12px', borderBottom: '1px solid #0a0d1a' }}>
              <div style={{ height: '10px', background: '#0d1117', borderRadius: '1px', marginBottom: '5px', width: `${60 + i * 5}%`, opacity: 0.4 + i * 0.08 }} />
              <div style={{ height: '8px', background: '#0a0e18', borderRadius: '1px', width: '30%' }} />
            </div>
          ))
        ) : error ? (
          <div style={{ padding: '16px 12px', fontSize: '9px', color: '#ff3b3b', letterSpacing: '0.15em' }}>
            ⚠ LOAD FAILED
          </div>
        ) : questions.length === 0 ? (
          <div style={{ padding: '16px 12px' }}>
            <div style={{ fontSize: '9px', color: '#1a2040', letterSpacing: '0.2em' }}>NO QUESTIONS YET</div>
            <div style={{ marginTop: '6px', fontSize: '8px', color: '#0f1428', letterSpacing: '0.1em' }}>scraper has not run</div>
          </div>
        ) : (
          questions.map((q) => (
            <QuestionRow key={q.id} question={q} inPair={pairIds.has(q.id)} />
          ))
        )}
      </div>
    </div>
  );
}
