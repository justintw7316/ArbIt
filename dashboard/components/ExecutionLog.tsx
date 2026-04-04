'use client'
import { useState, useEffect } from 'react'
import { useCounter } from '@/lib/useCounter'
import { EXECUTIONS } from '@/lib/mockData'

const MONO = 'JetBrains Mono, monospace'
const SANS = 'Inter, sans-serif'

function StatCard({ label, value, valueColor = '#fff' }: { label: string; value: string; valueColor?: string }) {
  return (
    <div style={{
      flex: 1,
      background: '#0A0A0A',
      border: '1px solid #1A1A1A',
      padding: '14px 18px',
    }}>
      <div style={{ fontFamily: SANS, fontSize: 10, fontWeight: 600, color: '#888', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontFamily: MONO, fontSize: 28, fontWeight: 700, color: valueColor, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { color: string; bg: string; label: string }> = {
    CONFIRMED: { color: '#00FF88', bg: 'rgba(0,255,136,0.08)',  label: '● CONFIRMED' },
    PENDING:   { color: '#FFB800', bg: 'rgba(255,184,0,0.08)',  label: '◌ PENDING'  },
    FAILED:    { color: '#FF3355', bg: 'rgba(255,51,85,0.08)',  label: '✕ FAILED'   },
  }
  const s = map[status] ?? map.FAILED
  return (
    <span style={{
      fontFamily: MONO, fontSize: 10, fontWeight: 600,
      color: s.color, background: s.bg,
      border: `1px solid ${s.color}33`,
      borderRadius: 3, padding: '3px 8px', letterSpacing: '0.08em',
    }}>
      {s.label}
    </span>
  )
}

const COLS = ['TIME', 'EVENT', 'POLY SIDE', 'KALSHI SIDE', 'SPREAD', 'NET P&L', 'STATUS']

export default function ExecutionLog() {
  const confirmed = EXECUTIONS.filter((e) => e.status === 'CONFIRMED')
  const [profitTarget, setProfitTarget] = useState(confirmed.reduce((s, e) => s + e.netPnl, 0))
  const animatedProfit = useCounter(profitTarget, 800)

  useEffect(() => {
    const t = setInterval(() => setProfitTarget((p) => p + Math.random() * 8 + 1), 5000)
    return () => clearInterval(t)
  }, [])

  const totalTrades = EXECUTIONS.length
  const successRate = ((confirmed.length / totalTrades) * 100).toFixed(1)

  return (
    <div>
      {/* Sticky header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '14px 20px 12px',
        borderBottom: '1px solid #1A1A1A',
        background: '#000',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <span style={{ fontFamily: SANS, fontSize: 13, fontWeight: 700, color: '#fff', letterSpacing: '0.01em' }}>
          EXECUTION LOG
        </span>
        <span style={{
          fontFamily: MONO, fontSize: 11,
          background: '#111', color: '#888',
          borderRadius: 3, padding: '1px 7px',
          border: '1px solid #1A1A1A',
        }}>
          {totalTrades} trades
        </span>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 1, padding: '16px 20px', background: '#000', borderBottom: '1px solid #1A1A1A' }}>
        <StatCard label="Total Trades"  value={String(totalTrades)} />
        <div style={{ width: 1, background: '#1A1A1A', flexShrink: 0 }} />
        <StatCard label="Total Profit"  value={`$${animatedProfit.toFixed(2)}`} valueColor="#00FF88" />
        <div style={{ width: 1, background: '#1A1A1A', flexShrink: 0 }} />
        <StatCard label="Success Rate"  value={`${successRate}%`} valueColor={parseFloat(successRate) > 80 ? '#00FF88' : '#FFB800'} />
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'auto' }}>
          <thead>
            <tr style={{ background: '#000', borderBottom: '1px solid #1A1A1A' }}>
              {COLS.map((col) => (
                <th key={col} style={{
                  fontFamily: SANS, fontSize: 11, fontWeight: 600,
                  color: '#888', letterSpacing: '0.1em',
                  textAlign: 'left', padding: '9px 16px', whiteSpace: 'nowrap',
                  textTransform: 'uppercase',
                }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {EXECUTIONS.map((exec, i) => {
              const pnlColor = exec.netPnl >= 0 ? '#00FF88' : '#FF3355'
              return (
                <tr
                  key={exec.id}
                  className="row-enter"
                  style={{
                    animationDelay: `${i * 30}ms`,
                    borderBottom: '1px solid #1A1A1A',
                    transition: 'background 0.12s',
                    cursor: 'default',
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = '#0D0D0D' }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'transparent' }}
                >
                  <td style={{ fontFamily: MONO, fontSize: 11, color: '#666', padding: '11px 16px', whiteSpace: 'nowrap' }}>
                    {exec.time}
                  </td>
                  <td style={{ fontFamily: SANS, fontSize: 13, color: '#CCCCCC', padding: '11px 16px', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={exec.event}>
                    {exec.event}
                  </td>
                  <td style={{ fontFamily: MONO, fontSize: 12, color: '#7B3FE4', padding: '11px 16px', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {exec.polymarketSide}
                  </td>
                  <td style={{ fontFamily: MONO, fontSize: 12, color: '#0066FF', padding: '11px 16px', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {exec.kalshiSide}
                  </td>
                  <td style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600, color: '#fff', padding: '11px 16px', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {exec.grossSpread.toFixed(1)}%
                  </td>
                  <td style={{ fontFamily: MONO, fontSize: 13, fontWeight: 700, color: pnlColor, padding: '11px 16px', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {exec.netPnl >= 0 ? '+' : ''}${exec.netPnl.toFixed(2)}
                  </td>
                  <td style={{ padding: '11px 16px', whiteSpace: 'nowrap' }}>
                    <StatusPill status={exec.status} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
