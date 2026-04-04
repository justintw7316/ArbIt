'use client'
import { useState, useEffect } from 'react'
import { useCounter } from '@/lib/useCounter'
import { OPPORTUNITIES } from '@/lib/mockData'

const MONO = 'JetBrains Mono, monospace'
const SANS = 'Inter, sans-serif'

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontFamily: SANS, fontSize: 10, fontWeight: 600, color: '#888', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 5 }}>
      {children}
    </div>
  )
}

function Section({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: '14px 16px', borderBottom: '1px solid #1A1A1A' }}>
      {children}
    </div>
  )
}

export default function Sidebar() {
  const [syncSeconds, setSyncSeconds] = useState(12)
  const [profitTarget, setProfitTarget] = useState(4847.32)
  const [minSpread, setMinSpread] = useState(3)
  const [minConfidence, setMinConfidence] = useState(70)
  const animatedProfit = useCounter(profitTarget, 1000)

  useEffect(() => {
    const t = setInterval(() => setSyncSeconds((s) => (s >= 60 ? 0 : s + 1)), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const t = setInterval(() => setProfitTarget((p) => p + Math.random() * 12 + 1), 8000)
    return () => clearInterval(t)
  }, [])

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  const liveCount = OPPORTUNITIES.filter((o) => o.status === 'live').length

  const connections = [
    { label: 'Polymarket', dotColor: '#7B3FE4', statusText: 'Connected', statusColor: '#00FF88' },
    { label: 'Kalshi',     dotColor: '#0066FF', statusText: 'Connected', statusColor: '#00FF88' },
    { label: 'Gemini API', dotColor: '#00AAFF', statusText: 'Active',    statusColor: '#00AAFF' },
  ]

  return (
    <div style={{
      width: 220,
      height: '100%',
      background: '#000',
      borderRight: '1px solid #1A1A1A',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      overflow: 'hidden',
    }}>

      {/* Logo */}
      <div style={{ padding: '16px 16px 14px', borderBottom: '1px solid #1A1A1A' }}>
        <div style={{ fontFamily: SANS, fontSize: 17, fontWeight: 800, letterSpacing: '-0.01em', lineHeight: 1 }}>
          <span style={{ color: '#fff' }}>Arb</span>
          <span style={{ color: '#00FF88' }}>it</span>
        </div>
        <div style={{ fontFamily: SANS, fontSize: 8, fontWeight: 600, color: '#666', letterSpacing: '0.2em', marginTop: 4 }}>
          PREDICTION MARKET ARBITRAGE
        </div>
      </div>

      {/* System status */}
      <Section>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
          <span className="live-dot" />
          <span style={{ fontFamily: SANS, fontSize: 10, fontWeight: 600, color: '#00FF88', letterSpacing: '0.08em' }}>
            SYSTEM ONLINE
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {connections.map((c) => (
            <div key={c.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontFamily: SANS, fontSize: 11, color: '#CCCCCC' }}>{c.label}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{ position: 'relative', width: 6, height: 6 }}>
                  <div className="ping-dot" style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: c.dotColor }} />
                </div>
                <span style={{ fontFamily: SANS, fontSize: 10, color: c.statusColor }}>{c.statusText}</span>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Stats */}
      <Section>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <Label>Active Opportunities</Label>
            <div style={{ fontFamily: MONO, fontSize: 28, fontWeight: 700, color: '#00FF88', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
              {liveCount}
            </div>
          </div>
          <div>
            <Label>Total Profit Today</Label>
            <div style={{ fontFamily: MONO, fontSize: 28, fontWeight: 700, color: '#00FF88', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
              ${animatedProfit.toFixed(2)}
            </div>
          </div>
          <div>
            <Label>Success Rate</Label>
            <div style={{ fontFamily: MONO, fontSize: 28, fontWeight: 700, color: '#fff', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
              78.6%
            </div>
          </div>
        </div>
      </Section>

      {/* Sliders */}
      <Section>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
              <Label>Min Spread</Label>
              <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: '#00FF88' }}>{minSpread}%</span>
            </div>
            <input
              type="range" min={0} max={20} value={minSpread}
              onChange={(e) => setMinSpread(Number(e.target.value))}
              style={{ background: `linear-gradient(to right, #00FF88 ${(minSpread / 20) * 100}%, #1A1A1A ${(minSpread / 20) * 100}%)` }}
            />
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
              <Label>Min Confidence</Label>
              <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: '#00FF88' }}>{minConfidence}%</span>
            </div>
            <input
              type="range" min={0} max={100} value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              style={{ background: `linear-gradient(to right, #00FF88 ${minConfidence}%, #1A1A1A ${minConfidence}%)` }}
            />
          </div>
        </div>
      </Section>

      {/* Footer */}
      <div style={{ marginTop: 'auto', padding: '10px 16px', borderTop: '1px solid #1A1A1A' }}>
        <span style={{ fontFamily: MONO, fontSize: 9, color: '#666' }}>
          SYNC <span style={{ color: '#888' }}>{fmt(syncSeconds)}</span> AGO
        </span>
      </div>

    </div>
  )
}
