import type { ArbitrageSignal } from '../../lib/types';

const MARKET_COLOR: Record<string, string> = {
  polymarket: '#4fc3f7',
  kalshi: '#ff9800',
  manifold: '#a78bfa',
};
const MARKET_LABEL: Record<string, string> = {
  polymarket: 'POLYMARKET',
  kalshi: 'KALSHI',
  manifold: 'MANIFOLD',
};
const MARKET_GLOW: Record<string, string> = {
  polymarket: '0 0 20px rgba(79,195,247,0.3)',
  kalshi: '0 0 20px rgba(255,152,0,0.3)',
  manifold: '0 0 20px rgba(167,139,250,0.3)',
};

function MarketCard({ market, text, price }: { market: string; text: string; price: number }) {
  const color = MARKET_COLOR[market] ?? '#94a3b8';
  const label = MARKET_LABEL[market] ?? market.toUpperCase();
  const glow = MARKET_GLOW[market] ?? 'none';
  const pct = Math.round(price * 100);

  return (
    <div style={{
      flex: 1,
      background: 'linear-gradient(135deg, #070a14 0%, #060810 100%)',
      border: '1px solid #0f1428',
      borderLeft: `3px solid ${color}`,
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Subtle corner accent */}
      <div style={{
        position: 'absolute',
        top: 0, right: 0,
        width: '40px', height: '40px',
        background: `linear-gradient(225deg, ${color}10, transparent)`,
      }} />

      {/* Platform label */}
      <span style={{
        fontSize: '8px',
        fontWeight: '600',
        color,
        letterSpacing: '0.25em',
        textShadow: glow,
      }}>
        ◆ {label}
      </span>

      {/* Question text */}
      <p style={{
        margin: 0,
        fontSize: '12px',
        color: '#c0c8d8',
        lineHeight: 1.6,
        flex: 1,
        letterSpacing: '0.01em',
      }}>
        {text}
      </p>

      {/* Probability */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
        <span style={{
          fontSize: '48px',
          fontWeight: '700',
          color,
          lineHeight: 1,
          letterSpacing: '-0.04em',
          textShadow: glow,
          fontVariantNumeric: 'tabular-nums',
        }}>
          {pct}
        </span>
        <span style={{ fontSize: '18px', color, opacity: 0.7, fontWeight: '300' }}>%</span>
      </div>
    </div>
  );
}

export interface SignalDetailProps {
  signal: ArbitrageSignal | null;
}

export default function SignalDetail({ signal }: SignalDetailProps) {
  if (!signal) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#060810',
      }}>
        <span style={{ color: '#0f1428', fontSize: '9px', letterSpacing: '0.3em' }}>SELECT A SIGNAL</span>
      </div>
    );
  }

  const spread = Math.round(signal.raw_spread * 100);

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      background: '#060810',
    }}>
      {/* Header bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        height: '36px',
        borderBottom: '1px solid #0a0d1a',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: '8px', color: '#1a2040', letterSpacing: '0.3em' }}>
          SIGNAL DETAIL
        </span>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
          <span style={{ fontSize: '9px', color: '#1a2040', letterSpacing: '0.15em' }}>EV</span>
          <span
            className="glow-orange"
            style={{
              fontSize: '28px',
              fontWeight: '700',
              color: '#ff6b35',
              letterSpacing: '-0.03em',
              lineHeight: 1,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            ${signal.expected_profit.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Market cards */}
      <div style={{
        display: 'flex',
        gap: '12px',
        padding: '16px 20px',
        flexShrink: 0,
      }}>
        <MarketCard market={signal.platform_a} text={signal.text_a} price={signal.price_a} />
        <MarketCard market={signal.platform_b} text={signal.text_b} price={signal.price_b} />
      </div>

      {/* Stats strip */}
      <div style={{
        display: 'flex',
        margin: '0 20px',
        border: '1px solid #0a0d1a',
        background: '#040608',
        flexShrink: 0,
      }}>
        {[
          { label: 'CONFIDENCE', value: (signal.confidence * 100).toFixed(1) + '%', color: '#ff6b35', glow: 'glow-orange' },
          { label: 'PRICE SPREAD', value: `+${spread}pp`, color: '#00e676', glow: 'glow-green' },
          { label: 'KELLY SIZE', value: `$${signal.recommended_size_usd.toFixed(0)}`, color: '#4fc3f7', glow: '' },
          { label: 'CONV. PROB', value: (signal.regression_convergence_prob * 100).toFixed(1) + '%', color: '#2a3060', glow: '' },
        ].map(({ label, value, color, glow }, i) => (
          <div key={i} style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            padding: '10px 0',
            borderRight: i < 3 ? '1px solid #0a0d1a' : 'none',
          }}>
            <span className={glow} style={{ fontSize: '13px', fontWeight: '500', color, letterSpacing: '-0.01em' }}>
              {value}
            </span>
            <span style={{ fontSize: '7px', color: '#1a2040', letterSpacing: '0.2em', marginTop: '3px' }}>
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
