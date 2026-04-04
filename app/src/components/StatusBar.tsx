import type { AppConfig } from '../lib/types';

interface StatusBarProps {
  config: AppConfig | null;
  error: boolean;
}

function Field({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <span style={{ color: '#2a3060', fontSize: '9px', letterSpacing: '0.15em' }}>{label}</span>
      <span style={{ color: valueColor ?? '#4a5568', fontSize: '9px', letterSpacing: '0.1em' }}>{value}</span>
    </span>
  );
}

export default function StatusBar({ config, error }: StatusBarProps) {
  const dbColor =
    config?.db_status === 'connected' ? '#00e676' :
    config?.db_status === 'disconnected' ? '#ff9800' : '#ff3b3b';

  const dbLabel =
    config?.db_status === 'connected' ? 'CONNECTED' :
    config?.db_status === 'disconnected' ? 'DISCONNECTED' :
    error ? 'ERROR' : 'CONNECTING';

  return (
    <footer style={{
      display: 'flex',
      alignItems: 'center',
      gap: '24px',
      height: '24px',
      padding: '0 16px',
      borderTop: '1px solid #0f1428',
      background: '#040608',
      flexShrink: 0,
    }}>
      <Field label="MDL" value={config?.embedding_model ?? '---'} />
      <span style={{ color: '#0f1428', fontSize: '9px' }}>·</span>
      <Field label="THR" value={config ? String(config.similarity_threshold) : '---'} />
      <span style={{ color: '#0f1428', fontSize: '9px' }}>·</span>
      <Field label="DB" value={dbLabel} valueColor={dbColor} />
      <span style={{ color: '#0f1428', fontSize: '9px' }}>·</span>
      <Field label="MKT" value={config?.markets?.map(m => m.slice(0,4).toUpperCase()).join(' ') ?? '---'} />
      <span style={{ marginLeft: 'auto', color: '#1a2040', fontSize: '8px', letterSpacing: '0.2em' }}>
        ARBX v1.0
      </span>
    </footer>
  );
}
