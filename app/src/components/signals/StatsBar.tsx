import type { SignalsStats } from '../../lib/types';

export type SignalsRankingMode = 'profit' | 'diverse';

interface StatsBarProps {
  stats: SignalsStats | null;
  loading: boolean;
  ranking: SignalsRankingMode;
  onRankingChange: (mode: SignalsRankingMode) => void;
}

function Stat({
  label, value, sub, color, glowClass, borderColor
}: {
  label: string;
  value: string;
  sub?: string;
  color: string;
  glowClass?: string;
  borderColor?: string;
}) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      padding: '0 20px',
      borderRight: `1px solid #0f1428`,
      borderLeft: borderColor ? `2px solid ${borderColor}` : undefined,
      minWidth: '80px',
      gap: '2px',
    }}>
      <span
        className={glowClass}
        style={{
          fontSize: '22px',
          fontWeight: '600',
          color,
          lineHeight: 1,
          fontVariantNumeric: 'tabular-nums',
          letterSpacing: '-0.02em',
        }}
      >
        {value}
      </span>
      <span style={{ fontSize: '8px', color: '#2a3060', letterSpacing: '0.2em', fontWeight: '400' }}>
        {label}
        {sub && <span style={{ color: '#1a2040', marginLeft: '4px' }}>{sub}</span>}
      </span>
    </div>
  );
}

export default function StatsBar({ stats, loading, ranking, onRankingChange }: StatsBarProps) {
  const dash = '--';

  return (
    <div style={{
      display: 'flex',
      height: '52px',
      borderBottom: '1px solid #0f1428',
      background: 'linear-gradient(180deg, #070a14 0%, #060810 100%)',
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      {/* Left accent */}
      <div style={{ width: '3px', background: 'linear-gradient(180deg, #ff6b35, rgba(255,107,53,0.2))', flexShrink: 0 }} />

      {loading || !stats ? (
        <div style={{ display: 'flex', alignItems: 'center', padding: '0 20px' }}>
          <span style={{ color: '#1a2040', fontSize: '9px', letterSpacing: '0.3em' }}>LOADING</span>
        </div>
      ) : (
        <>
          <Stat label="SIGNALS" value={String(stats.total)} color="#ff6b35" glowClass={stats.total > 0 ? 'glow-orange' : ''} borderColor="#ff6b35" />
          <Stat label="TOTAL EV" sub="$" value={stats.total_ev > 0 ? `$${stats.total_ev.toFixed(2)}` : dash} color={stats.total_ev > 0 ? '#00e676' : '#1a2040'} glowClass={stats.total_ev > 0 ? 'glow-green' : ''} />
          <Stat label="TOP EV" sub="$" value={stats.top_ev > 0 ? `$${stats.top_ev.toFixed(2)}` : dash} color={stats.top_ev > 0 ? '#00e676' : '#1a2040'} glowClass={stats.top_ev > 0 ? 'glow-green' : ''} />

          <div style={{ width: '1px', background: '#1a2040', margin: '10px 0' }} />

          <Stat label="AVG CONF" value={stats.avg_confidence > 0 ? stats.avg_confidence.toFixed(3) : dash} color={stats.avg_confidence > 0 ? '#ff6b35' : '#1a2040'} glowClass={stats.avg_confidence > 0 ? 'glow-orange' : ''} />
          <Stat label="AVG SPREAD" sub="pp" value={stats.avg_spread > 0 ? `+${Math.round(stats.avg_spread * 100)}` : dash} color={stats.avg_spread > 0 ? '#00e676' : '#1a2040'} glowClass={stats.avg_spread > 0 ? 'glow-green' : ''} />

          {/* Ranking toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '0 16px', marginLeft: 'auto' }}>
            {(['profit', 'diverse'] as SignalsRankingMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => onRankingChange(mode)}
                style={{
                  padding: '3px 10px',
                  fontSize: '8px',
                  letterSpacing: '0.15em',
                  fontFamily: 'IBM Plex Mono, monospace',
                  background: ranking === mode ? 'rgba(255,107,53,0.15)' : 'transparent',
                  border: `1px solid ${ranking === mode ? '#ff6b35' : '#1a2040'}`,
                  color: ranking === mode ? '#ff6b35' : '#2a3060',
                  cursor: 'pointer',
                  transition: 'all 0.1s',
                  textTransform: 'uppercase',
                }}
              >
                {mode}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
