import type { ArbitrageSignal } from '../../lib/types';

const MARKET_COLOR: Record<string, string> = {
  polymarket: '#4fc3f7',
  kalshi: '#ff9800',
  manifold: '#a78bfa',
};
const MARKET_SHORT: Record<string, string> = {
  polymarket: 'POLY',
  kalshi: 'KALS',
  manifold: 'MANIF',
};

interface SignalRowProps {
  signal: ArbitrageSignal;
  selected: boolean;
  onClick: () => void;
  index: number;
}

export default function SignalRow({ signal, selected, onClick, index }: SignalRowProps) {
  const spread = Math.round(signal.raw_spread * 100);
  const ev = signal.expected_profit;
  const accentColor = '#ff6b35';
  const scoreColor = '#ff6b35';
  const glowClass = 'glow-orange';

  const mA = signal.platform_a;
  const mB = signal.platform_b;
  const colA = MARKET_COLOR[mA] ?? '#94a3b8';
  const colB = MARKET_COLOR[mB] ?? '#94a3b8';

  return (
    <button
      onClick={onClick}
      className="fade-in-row"
      style={{
        animationDelay: `${index * 30}ms`,
        width: '100%',
        textAlign: 'left',
        display: 'block',
        padding: '10px 12px 10px 14px',
        borderBottom: '1px solid #0a0d1a',
        borderLeft: `3px solid ${selected ? accentColor : 'transparent'}`,
        background: selected
          ? `linear-gradient(90deg, rgba(255,107,53,0.06) 0%, transparent 100%)`
          : 'transparent',
        cursor: 'pointer',
        transition: 'all 0.1s',
        fontFamily: 'IBM Plex Mono, monospace',
        position: 'relative',
      }}
      onMouseEnter={e => {
        if (!selected) {
          (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.02)';
          (e.currentTarget as HTMLButtonElement).style.borderLeftColor = 'rgba(255,107,53,0.3)';
        }
      }}
      onMouseLeave={e => {
        if (!selected) {
          (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
          (e.currentTarget as HTMLButtonElement).style.borderLeftColor = 'transparent';
        }
      }}
    >
      {/* EV + market route */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', marginBottom: '5px' }}>
        <span
          className={selected ? glowClass : ''}
          style={{
            fontSize: '18px',
            fontWeight: '600',
            color: scoreColor,
            lineHeight: 1,
            letterSpacing: '-0.02em',
            fontVariantNumeric: 'tabular-nums',
            minWidth: '48px',
          }}
        >
          ${ev.toFixed(2)}
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{
            fontSize: '8px',
            fontWeight: '600',
            color: colA,
            border: `1px solid ${colA}`,
            padding: '1px 5px',
            letterSpacing: '0.1em',
            opacity: 0.9,
          }}>
            {MARKET_SHORT[mA] ?? mA.toUpperCase()}
          </span>
          <span style={{ fontSize: '8px', color: '#2a3060' }}>→</span>
          <span style={{
            fontSize: '8px',
            fontWeight: '600',
            color: colB,
            border: `1px solid ${colB}`,
            padding: '1px 5px',
            letterSpacing: '0.1em',
            opacity: 0.9,
          }}>
            {MARKET_SHORT[mB] ?? mB.toUpperCase()}
          </span>
        </div>

        <span style={{ fontSize: '8px', color: '#2a3060', marginLeft: 'auto' }}>
          {(signal.confidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Question text */}
      <div style={{
        fontSize: '11px',
        color: selected ? '#e0e0e0' : '#5a6080',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        letterSpacing: '0.01em',
        lineHeight: 1.4,
      }}>
        {signal.text_a}
      </div>

      {/* Spread */}
      <div style={{
        marginTop: '3px',
        fontSize: '9px',
        color: 'rgba(0,230,118,0.6)',
        letterSpacing: '0.1em',
      }}>
        +{spread}pp spread
      </div>
    </button>
  );
}
