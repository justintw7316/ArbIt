interface PipelineLogProps {
  logs: string[];
}

export default function PipelineLog({ logs }: PipelineLogProps) {
  return (
    <div style={{
      margin: '0 20px 20px',
      border: '1px solid #0f1428',
      background: '#040608',
      display: 'flex',
      flexDirection: 'column',
      height: '200px',
    }}>
      <div style={{
        padding: '5px 12px',
        borderBottom: '1px solid #0a0d1a',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: '8px', color: '#00e676', letterSpacing: '0.25em', textShadow: '0 0 8px rgba(0,230,118,0.4)' }}>
          PIPELINE LOG
        </span>
        <span style={{ fontSize: '7px', color: '#1a2040', letterSpacing: '0.1em' }}>
          {logs.length} LINES
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
        {logs.length === 0 ? (
          <span style={{ fontSize: '9px', color: '#1a2040', letterSpacing: '0.15em' }}>NO LOG OUTPUT</span>
        ) : (
          logs.map((line, i) => (
            <span key={i} style={{
              fontSize: '10px',
              color: line.toLowerCase().includes('error') || line.toLowerCase().includes('fail')
                ? '#ff3b3b'
                : line.toLowerCase().includes('warn')
                ? '#ff9800'
                : '#00e676',
              lineHeight: 1.5,
              letterSpacing: '0.01em',
              opacity: 0.8,
            }}>
              {line}
            </span>
          ))
        )}
      </div>
    </div>
  );
}
