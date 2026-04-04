import type { PipelineStep } from '../../lib/types';

interface StepCardProps {
  step: PipelineStep;
  isLast: boolean;
}

const STATUS_CONFIG = {
  done: {
    color: '#00e676',
    glow: '0 0 12px rgba(0,230,118,0.5)',
    bg: 'rgba(0,230,118,0.04)',
    border: '#00e676',
    icon: '✓',
    dimColor: 'rgba(0,230,118,0.4)',
  },
  active: {
    color: '#ff6b35',
    glow: '0 0 12px rgba(255,107,53,0.5)',
    bg: 'rgba(255,107,53,0.06)',
    border: '#ff6b35',
    icon: '●',
    dimColor: 'rgba(255,107,53,0.4)',
  },
  pending: {
    color: '#2a3060',
    glow: 'none',
    bg: 'transparent',
    border: '#0f1428',
    icon: '○',
    dimColor: '#1a2040',
  },
  error: {
    color: '#ff3b3b',
    glow: '0 0 12px rgba(255,59,59,0.5)',
    bg: 'rgba(255,59,59,0.04)',
    border: '#ff3b3b',
    icon: '✗',
    dimColor: 'rgba(255,59,59,0.4)',
  },
} as const;

export default function StepCard({ step, isLast }: StepCardProps) {
  const cfg = STATUS_CONFIG[step.status] ?? STATUS_CONFIG.pending;
  const elapsedStr = step.elapsed_ms != null ? `${(step.elapsed_ms / 1000).toFixed(1)}s` : '--';
  const isActive = step.status === 'active';

  return (
    <div style={{ display: 'flex', alignItems: 'center', flex: 1, gap: '4px' }}>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        flex: 1,
        padding: '12px 8px',
        background: cfg.bg,
        border: `1px solid ${cfg.border}`,
        borderTop: `2px solid ${cfg.border}`,
        position: 'relative',
        overflow: 'hidden',
        minWidth: '70px',
        gap: '4px',
      }}>
        {/* Active pulse overlay */}
        {isActive && (
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(255,107,53,0.03)',
            animation: 'live-pulse 1.5s ease-in-out infinite',
          }} />
        )}

        {/* Step number */}
        <span style={{
          fontSize: '7px',
          color: cfg.dimColor,
          letterSpacing: '0.2em',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {String(step.number).padStart(2, '0')}
        </span>

        {/* Status icon */}
        <span style={{
          fontSize: '18px',
          color: cfg.color,
          textShadow: cfg.glow,
          lineHeight: 1,
          animation: isActive ? 'live-pulse 1.5s ease-in-out infinite' : 'none',
        }}>
          {cfg.icon}
        </span>

        {/* Step label */}
        <span style={{
          fontSize: '8px',
          fontWeight: '600',
          color: cfg.color,
          letterSpacing: '0.1em',
          textAlign: 'center',
          textShadow: step.status !== 'pending' ? cfg.glow : 'none',
          lineHeight: 1.3,
        }}>
          {step.short_label}
        </span>

        {/* Status/elapsed */}
        <span style={{
          fontSize: '7px',
          color: cfg.dimColor,
          letterSpacing: '0.15em',
          textAlign: 'center',
          maxWidth: '100%',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          padding: '0 4px',
        }}>
          {step.status === 'error' && step.message
            ? step.message.slice(0, 16)
            : step.status === 'pending'
            ? '—'
            : step.status.toUpperCase()}
        </span>

        {step.status !== 'pending' && step.status !== 'error' && (
          <span style={{
            fontSize: '7px',
            color: '#1a2040',
            letterSpacing: '0.1em',
            fontVariantNumeric: 'tabular-nums',
          }}>
            {elapsedStr}
          </span>
        )}
      </div>

      {/* Arrow connector */}
      {!isLast && (
        <span style={{ fontSize: '9px', color: '#1a2040', flexShrink: 0 }}>→</span>
      )}
    </div>
  );
}
