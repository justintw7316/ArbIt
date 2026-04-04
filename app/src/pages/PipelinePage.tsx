import { useEffect, useRef, useState } from 'react';
import type { PipelineStatus } from '../lib/types';
import { api } from '../lib/api';
import PipelineGrid from '../components/pipeline/PipelineGrid';
import PipelineLog from '../components/pipeline/PipelineLog';

export default function PipelinePage() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchStatus() {
    try {
      const data = await api.getPipelineStatus();
      setStatus(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 10_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        height: '36px',
        borderBottom: '1px solid #0a0d1a',
        flexShrink: 0,
        background: 'linear-gradient(180deg, #070a14 0%, #060810 100%)',
      }}>
        <span style={{ fontSize: '8px', color: '#1a2040', letterSpacing: '0.3em' }}>PIPELINE STATUS</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          {status?.last_run && (
            <span style={{ fontSize: '9px', color: '#2a3060', letterSpacing: '0.15em' }}>
              LAST RUN: {new Date(status.last_run).toLocaleTimeString('en-US', { hour12: false })}
            </span>
          )}
          {status?.total_runtime_ms != null && (
            <span style={{ fontSize: '9px', color: '#2a3060', letterSpacing: '0.15em' }}>
              TOTAL: {(status.total_runtime_ms / 1000).toFixed(1)}s
            </span>
          )}
        </div>
      </div>

      {error ? (
        <div style={{ padding: '20px', fontSize: '10px', color: '#ff3b3b', letterSpacing: '0.15em' }}>
          ⚠ CANNOT REACH PIPELINE STATUS ENDPOINT — {error}
        </div>
      ) : (
        <>
          <PipelineGrid status={status} loading={loading} />
          <PipelineLog logs={status?.logs ?? []} />
        </>
      )}
    </div>
  );
}
