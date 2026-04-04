import type { PipelineStatus } from '../../lib/types';
import StepCard from './StepCard';

interface PipelineGridProps {
  status: PipelineStatus | null;
  loading: boolean;
}

export default function PipelineGrid({ status, loading }: PipelineGridProps) {
  if (loading) {
    return (
      <div style={{ display: 'flex', gap: '4px', padding: '20px' }}>
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} style={{
            flex: 1,
            height: '120px',
            border: '1px solid #0f1428',
            background: '#070a14',
            opacity: 0.3 + i * 0.05,
          }} />
        ))}
      </div>
    );
  }

  if (!status || status.steps.length === 0) {
    return (
      <div style={{ padding: '20px' }}>
        <div style={{ fontSize: '9px', color: '#1a2040', letterSpacing: '0.2em' }}>PIPELINE HAS NOT RUN</div>
        <div style={{ marginTop: '6px', fontSize: '8px', color: '#0f1428', letterSpacing: '0.1em' }}>waiting for first execution</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'stretch', gap: '2px', padding: '16px 20px' }}>
      {status.steps.map((step, i) => (
        <StepCard key={step.number} step={step} isLast={i === status.steps.length - 1} />
      ))}
    </div>
  );
}
