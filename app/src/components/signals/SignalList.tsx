import type { ArbitrageSignal } from '../../lib/types';
import SignalRow from './SignalRow';

export interface SignalListProps {
  signals: ArbitrageSignal[];
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export default function SignalList({ signals, loading, error, selectedId, onSelect }: SignalListProps) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      width: '300px',
      minWidth: '260px',
      borderRight: '1px solid #0f1428',
      background: '#060810',
      height: '100%',
    }}>
      {/* List header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 12px',
        height: '32px',
        borderBottom: '1px solid #0a0d1a',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: '8px', color: '#2a3060', letterSpacing: '0.25em' }}>
          RANKED BY EV ▾
        </span>
        <span style={{ fontSize: '8px', color: '#2a3060', letterSpacing: '0.15em' }}>
          {signals.length} SIGNALS
        </span>
      </div>

      {/* List body */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} style={{ padding: '12px 14px', borderBottom: '1px solid #0a0d1a' }}>
              <div style={{ height: '18px', background: '#0d1117', borderRadius: '2px', marginBottom: '6px', width: '60%', opacity: 0.5 + i * 0.1 }} />
              <div style={{ height: '10px', background: '#0a0e18', borderRadius: '2px', width: '85%' }} />
            </div>
          ))
        ) : error ? (
          <div style={{ padding: '20px 14px' }}>
            <div style={{ fontSize: '9px', color: '#ff3b3b', letterSpacing: '0.15em', marginBottom: '8px' }}>⚠ FETCH ERROR</div>
            <div style={{ fontSize: '9px', color: '#2a3060' }}>{error}</div>
          </div>
        ) : signals.length === 0 ? (
          <div style={{ padding: '20px 14px' }}>
            <div style={{ fontSize: '9px', color: '#1a2040', letterSpacing: '0.2em' }}>NO SIGNALS</div>
            <div style={{ marginTop: '8px', fontSize: '8px', color: '#0f1428', letterSpacing: '0.1em' }}>
              pipeline has not run yet
            </div>
          </div>
        ) : (
          signals.map((signal, i) => (
            <SignalRow
              key={signal.pair_id}
              signal={signal}
              selected={signal.pair_id === selectedId}
              onClick={() => onSelect(signal.pair_id)}
              index={i}
            />
          ))
        )}
      </div>
    </div>
  );
}
