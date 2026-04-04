'use client'
import { useState } from 'react'
import {
  ComposedChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
  LineChart, Line,
} from 'recharts'
import { SPREAD_HISTORY } from '@/lib/mockData'
import type { SpreadPoint } from '@/lib/types'

const MONO = 'JetBrains Mono, monospace'
const SANS = 'Inter, sans-serif'

const PAIR_OPTIONS = [
  { label: 'BTC >$100K by EOY',        id: 'btc'    },
  { label: 'Fed Rate Cut June 2024',    id: 'fed'    },
  { label: 'Biden 2024 Election Win',   id: 'biden'  },
  { label: 'Starship Orbital 2024',     id: 'star'   },
  { label: 'S&P 500 hits 6000',         id: 'sp500'  },
]

// Spread events table data
const SPREAD_EVENTS = [
  { time: '11:43:07', pair: 'Fed Rate Cut × FOMC June',       peakSpread: '6.0%', duration: '14m 22s', estProfit: '$847',  status: 'CAPTURED' },
  { time: '11:38:22', pair: 'BTC $100K × Year-End',           peakSpread: '7.0%', duration: '22m 08s', estProfit: '$613',  status: 'CAPTURED' },
  { time: '11:28:44', pair: 'Starship Orbital × 2024',        peakSpread: '7.0%', duration: '31m 55s', estProfit: '$522',  status: 'CAPTURED' },
  { time: '11:22:11', pair: 'Apple Vision Pro × 500K',        peakSpread: '5.9%', duration: '18m 40s', estProfit: '$389',  status: 'CAPTURED' },
  { time: '10:58:34', pair: 'GPT-5 Release × 2024',           peakSpread: '4.2%', duration: '09m 12s', estProfit: '$299',  status: 'CAPTURED' },
  { time: '10:47:21', pair: 'S&P 500 × 6000 EOY',             peakSpread: '3.5%', duration: '06m 44s', estProfit: '$216',  status: 'CAPTURED' },
  { time: '10:15:00', pair: 'Biden 2024 × Senate Dems',       peakSpread: '2.3%', duration: '04m 30s', estProfit: '$94',   status: 'MISSED'   },
  { time: '09:54:30', pair: 'BTC $100K × Hedged NO',          peakSpread: '7.0%', duration: '02m 11s', estProfit: '-$9',   status: 'MISSED'   },
  { time: '09:41:16', pair: 'Starship Orbital × Init',        peakSpread: '6.9%', duration: '28m 03s', estProfit: '$388',  status: 'CAPTURED' },
  { time: '09:28:03', pair: 'Senate Dems × Majority',         peakSpread: '2.3%', duration: '11m 22s', estProfit: '$143',  status: 'CAPTURED' },
  { time: '11:31:07', pair: 'Biden 2024 Win × Kalshi',        peakSpread: '7.0%', duration: '—',       estProfit: '—',     status: 'OPEN'     },
  { time: '11:15:33', pair: 'Senate Dems × Senate Control',   peakSpread: '2.0%', duration: '—',       estProfit: '—',     status: 'OPEN'     },
]

// Arbitrage window timeline blocks (minutes into the 24h day, width = duration in minutes)
const ARB_WINDOWS = [
  { start: 18, width: 22, spread: 7.0, pair: 'BTC $100K',      status: 'captured' },
  { start: 52, width: 14, spread: 6.0, pair: 'Fed Rate Cut',   status: 'captured' },
  { start: 88, width: 32, spread: 7.0, pair: 'Starship',       status: 'captured' },
  { start: 130, width: 9, spread: 4.2, pair: 'GPT-5 Release',  status: 'captured' },
  { start: 155, width: 4, spread: 2.3, pair: 'Senate Dems',    status: 'missed'   },
  { start: 175, width: 7, spread: 3.5, pair: 'S&P 500 6K',     status: 'captured' },
  { start: 210, width: 28, spread: 6.9, pair: 'Starship Init', status: 'captured' },
  { start: 260, width: 2, spread: 7.0, pair: 'BTC Hedged',     status: 'missed'   },
  { start: 288, width: 11, spread: 2.3, pair: 'Senate Mon.',   status: 'captured' },
  { start: 340, width: 19, spread: 5.9, pair: 'Vision Pro',    status: 'captured' },
  { start: 391, width: 31, spread: 7.0, pair: 'Biden 2024',    status: 'captured' },
  { start: 443, width: 8, spread: 7.0, pair: 'Fed Rate [open]',status: 'open'     },
]

const TIMELINE_TOTAL = 480 // 8 hours shown

interface TooltipProps {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}

function CustomTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null
  const poly   = payload.find((p) => p.name === 'polyPrice')
  const kalshi = payload.find((p) => p.name === 'kalshiPrice')
  const spread = poly && kalshi ? Math.abs(poly.value - kalshi.value) : 0

  return (
    <div style={{
      background: '#0A0A0A',
      border: '1px solid #1A1A1A',
      borderRadius: 3,
      padding: '10px 14px',
      minWidth: 160,
    }}>
      <div style={{ fontFamily: MONO, fontSize: 10, color: '#888', marginBottom: 8, letterSpacing: '0.1em' }}>
        {label}
      </div>
      {poly && (
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 3 }}>
          <span style={{ fontFamily: MONO, fontSize: 11, color: '#7B3FE4' }}>POLY</span>
          <span style={{ fontFamily: MONO, fontSize: 11, color: '#7B3FE4', fontVariantNumeric: 'tabular-nums' }}>{poly.value.toFixed(3)}</span>
        </div>
      )}
      {kalshi && (
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 3 }}>
          <span style={{ fontFamily: MONO, fontSize: 11, color: '#0066FF' }}>KALSHI</span>
          <span style={{ fontFamily: MONO, fontSize: 11, color: '#0066FF', fontVariantNumeric: 'tabular-nums' }}>{kalshi.value.toFixed(3)}</span>
        </div>
      )}
      <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid #1A1A1A', display: 'flex', justifyContent: 'space-between', gap: 16 }}>
        <span style={{ fontFamily: MONO, fontSize: 11, color: '#00FF88' }}>SPREAD</span>
        <span style={{ fontFamily: MONO, fontSize: 11, color: '#00FF88', fontVariantNumeric: 'tabular-nums' }}>{(spread * 100).toFixed(2)}pp</span>
      </div>
    </div>
  )
}

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const chartData = data.map((v, i) => ({ i, v }))
  return (
    <div style={{ width: 60, height: 24 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 2 }}>
          <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function StatCard({
  label, value, valueColor, sparkData, sparkColor, unit
}: {
  label: string; value: string; valueColor: string;
  sparkData: number[]; sparkColor: string; unit?: string
}) {
  return (
    <div style={{ flex: 1, padding: '14px 16px', borderRight: '1px solid #1A1A1A' }}>
      <div style={{ fontFamily: SANS, fontSize: 10, fontWeight: 600, color: '#888', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8 }}>
        <div>
          <div style={{ fontFamily: MONO, fontSize: 20, fontWeight: 700, color: valueColor, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
            {value}
          </div>
          {unit && (
            <div style={{ fontFamily: MONO, fontSize: 9, color: '#666', marginTop: 3 }}>{unit}</div>
          )}
        </div>
        <Sparkline data={sparkData} color={sparkColor} />
      </div>
    </div>
  )
}

// Derive sparklines from SPREAD_HISTORY last 12 points
const lastN = SPREAD_HISTORY.slice(-12)
const spreadSpark   = lastN.map((p: SpreadPoint) => p.spread * 100)
const polySpark     = lastN.map((p: SpreadPoint) => p.polyPrice)
const kalshiSpark   = lastN.map((p: SpreadPoint) => p.kalshiPrice)
const maxSpreadSpark = [...spreadSpark]
const minSpreadSpark = [...spreadSpark]

export default function SpreadHistory() {
  const [selectedPair, setSelectedPair] = useState(PAIR_OPTIONS[0].id)
  const [hoveredWindow, setHoveredWindow] = useState<number | null>(null)

  const currentSpread = (SPREAD_HISTORY[SPREAD_HISTORY.length - 1]?.spread * 100).toFixed(2)
  const maxSpread     = (Math.max(...SPREAD_HISTORY.map((p: SpreadPoint) => p.spread)) * 100).toFixed(2)
  const minSpread     = (Math.min(...SPREAD_HISTORY.map((p: SpreadPoint) => p.spread)) * 100).toFixed(2)
  const avgPoly       = (SPREAD_HISTORY.reduce((s: number, p: SpreadPoint) => s + p.polyPrice, 0) / SPREAD_HISTORY.length).toFixed(3)
  const avgKalshi     = (SPREAD_HISTORY.reduce((s: number, p: SpreadPoint) => s + p.kalshiPrice, 0) / SPREAD_HISTORY.length).toFixed(3)

  // Filter X-axis to every 3 hours (every 6th point in 30-min intervals)
  const xTicks = SPREAD_HISTORY
    .filter((_: SpreadPoint, i: number) => i % 6 === 0)
    .map((p: SpreadPoint) => p.time)

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
          SPREAD HISTORY
        </span>
        <span style={{ fontFamily: MONO, fontSize: 10, color: '#666', letterSpacing: '0.1em' }}>24H</span>

        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginLeft: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 18, height: 2, background: '#7B3FE4' }} />
            <span style={{ fontFamily: MONO, fontSize: 10, color: '#888', letterSpacing: '0.08em' }}>POLY</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 18, height: 2, background: '#0066FF' }} />
            <span style={{ fontFamily: MONO, fontSize: 10, color: '#888', letterSpacing: '0.08em' }}>KALSHI</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 14, height: 8, background: 'rgba(0,255,136,0.15)', border: '1px solid rgba(0,255,136,0.25)' }} />
            <span style={{ fontFamily: MONO, fontSize: 10, color: '#888', letterSpacing: '0.08em' }}>SPREAD</span>
          </div>
        </div>

        {/* Pair selector */}
        <select
          value={selectedPair}
          onChange={(e) => setSelectedPair(e.target.value)}
          style={{
            marginLeft: 'auto',
            fontFamily: MONO, fontSize: 11,
            color: '#ccc',
            background: '#0A0A0A',
            border: '1px solid #1A1A1A',
            borderRadius: 3,
            padding: '5px 10px',
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          {PAIR_OPTIONS.map((opt) => (
            <option key={opt.id} value={opt.id} style={{ background: '#0A0A0A' }}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* ── Stat cards ── */}
      <div style={{ display: 'flex', borderBottom: '1px solid #1A1A1A' }}>
        <StatCard label="Current Spread"  value={`${currentSpread}pp`} valueColor="#00FF88" sparkData={spreadSpark}    sparkColor="#00FF88" unit="live" />
        <StatCard label="Max Spread 24H"  value={`${maxSpread}pp`}     valueColor="#fff"    sparkData={maxSpreadSpark} sparkColor="#fff"    />
        <StatCard label="Min Spread 24H"  value={`${minSpread}pp`}     valueColor="#888"    sparkData={minSpreadSpark} sparkColor="#888"    />
        <StatCard label="Avg Poly Price"  value={avgPoly}              valueColor="#7B3FE4" sparkData={polySpark}      sparkColor="#7B3FE4" unit="probability" />
        <div style={{ flex: 1, padding: '14px 16px' }}>
          <div style={{ fontFamily: SANS, fontSize: 10, fontWeight: 600, color: '#888', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
            Avg Kalshi Price
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8 }}>
            <div>
              <div style={{ fontFamily: MONO, fontSize: 20, fontWeight: 700, color: '#0066FF', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
                {avgKalshi}
              </div>
              <div style={{ fontFamily: MONO, fontSize: 9, color: '#666', marginTop: 3 }}>probability</div>
            </div>
            <Sparkline data={kalshiSpark} color="#0066FF" />
          </div>
        </div>
      </div>

      {/* ── Main chart ── */}
      <div style={{ padding: '20px 20px 4px', borderBottom: '1px solid #1A1A1A' }}>
        <div style={{ height: 360 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={SPREAD_HISTORY} margin={{ top: 8, right: 56, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="polyFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#7B3FE4" stopOpacity={0.12} />
                  <stop offset="100%" stopColor="#7B3FE4" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="kalshiFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0066FF" stopOpacity={0.10} />
                  <stop offset="100%" stopColor="#0066FF" stopOpacity={0.01} />
                </linearGradient>
                <linearGradient id="spreadFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00FF88" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#00FF88" stopOpacity={0.03} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="2 6" stroke="#1A1A1A" vertical={false} />

              <XAxis
                dataKey="time"
                ticks={xTicks}
                tick={{ fontFamily: MONO, fontSize: 9, fill: '#666' }}
                tickLine={false}
                axisLine={{ stroke: '#1A1A1A' }}
              />

              {/* Left Y axis: probability 0–1 */}
              <YAxis
                yAxisId="prob"
                orientation="left"
                domain={[0.2, 0.9]}
                tick={{ fontFamily: MONO, fontSize: 9, fill: '#666' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => v.toFixed(2)}
                width={38}
              />

              {/* Right Y axis: spread % */}
              <YAxis
                yAxisId="spread"
                orientation="right"
                domain={[0, 0.15]}
                tick={{ fontFamily: MONO, fontSize: 9, fill: '#666' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
                width={46}
              />

              <Tooltip
                content={<CustomTooltip />}
                cursor={{ stroke: '#333', strokeWidth: 1, strokeDasharray: '3 3' }}
              />

              {/* Min threshold line at 3% spread */}
              <ReferenceLine
                yAxisId="spread"
                y={0.03}
                stroke="#FFB800"
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{
                  value: 'MIN THRESHOLD 3%',
                  position: 'insideTopRight',
                  fontFamily: MONO,
                  fontSize: 8,
                  fill: '#FFB800',
                  dy: -6,
                }}
              />

              {/* Spread fill area on right axis */}
              <Area
                yAxisId="spread"
                type="monotone"
                dataKey="spread"
                stroke="none"
                fill="url(#spreadFill)"
                fillOpacity={1}
                isAnimationActive={false}
              />

              {/* Poly probability — purple */}
              <Area
                yAxisId="prob"
                type="monotone"
                dataKey="polyPrice"
                stroke="#7B3FE4"
                strokeWidth={2}
                fill="url(#polyFill)"
                fillOpacity={1}
                dot={false}
                activeDot={{ r: 4, fill: '#7B3FE4', strokeWidth: 0 }}
                isAnimationActive={false}
              />

              {/* Kalshi probability — blue */}
              <Area
                yAxisId="prob"
                type="monotone"
                dataKey="kalshiPrice"
                stroke="#0066FF"
                strokeWidth={2}
                fill="url(#kalshiFill)"
                fillOpacity={1}
                dot={false}
                activeDot={{ r: 4, fill: '#0066FF', strokeWidth: 0 }}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Opportunity Timeline ── */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #1A1A1A' }}>
        <div style={{ fontFamily: SANS, fontSize: 10, fontWeight: 600, color: '#888', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 10 }}>
          ARBITRAGE WINDOWS — LAST 8H
        </div>
        <div style={{ position: 'relative', height: 28, background: '#0A0A0A', border: '1px solid #1A1A1A', borderRadius: 2, overflow: 'hidden' }}>
          {/* Hour marks */}
          {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((h) => (
            <div key={h} style={{
              position: 'absolute',
              left: `${(h / 8) * 100}%`,
              top: 0, bottom: 0,
              borderLeft: h > 0 ? '1px solid #1A1A1A' : 'none',
              display: 'flex', alignItems: 'flex-end',
              paddingBottom: 2, paddingLeft: 3,
            }}>
              {h > 0 && (
                <span style={{ fontFamily: MONO, fontSize: 7, color: '#666' }}>{h}h</span>
              )}
            </div>
          ))}

          {ARB_WINDOWS.map((w, i) => {
            const left  = (w.start / TIMELINE_TOTAL) * 100
            const width = Math.max((w.width / TIMELINE_TOTAL) * 100, 0.4)
            const color = w.status === 'captured' ? '#00FF88'
                        : w.status === 'missed'   ? '#FF3355'
                        : '#FFB800'
            const isHov = hoveredWindow === i
            return (
              <div
                key={i}
                onMouseEnter={() => setHoveredWindow(i)}
                onMouseLeave={() => setHoveredWindow(null)}
                style={{
                  position: 'absolute',
                  left: `${left}%`,
                  width: `${width}%`,
                  top: 4, bottom: 4,
                  background: isHov ? color : `${color}55`,
                  borderRadius: 1,
                  cursor: 'default',
                  transition: 'background 0.12s',
                  borderTop: `2px solid ${color}`,
                }}
                title={`${w.pair} \u2014 ${w.spread.toFixed(1)}% spread`}
              />
            )
          })}

          {/* Tooltip for hovered window */}
          {hoveredWindow !== null && (() => {
            const w = ARB_WINDOWS[hoveredWindow]
            const left = (w.start / TIMELINE_TOTAL) * 100
            const color = w.status === 'captured' ? '#00FF88' : w.status === 'missed' ? '#FF3355' : '#FFB800'
            return (
              <div style={{
                position: 'absolute',
                left: `${Math.min(left, 72)}%`,
                top: '110%',
                background: '#0A0A0A',
                border: `1px solid ${color}44`,
                borderRadius: 3,
                padding: '6px 10px',
                zIndex: 20,
                pointerEvents: 'none',
                whiteSpace: 'nowrap',
              }}>
                <div style={{ fontFamily: MONO, fontSize: 10, color, fontWeight: 600 }}>{w.spread.toFixed(1)}% — {w.pair}</div>
                <div style={{ fontFamily: MONO, fontSize: 9, color: '#888', marginTop: 2 }}>{w.width}m window · {w.status.toUpperCase()}</div>
              </div>
            )
          })()}
        </div>
        {/* Legend */}
        <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
          {[['#00FF88', 'CAPTURED'], ['#FF3355', 'MISSED'], ['#FFB800', 'OPEN']].map(([color, label]) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 10, height: 10, background: `${color}55`, borderTop: `2px solid ${color}`, borderRadius: 1 }} />
              <span style={{ fontFamily: MONO, fontSize: 8, color: '#888', letterSpacing: '0.08em' }}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Spread Events Table ── */}
      <div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '12px 20px 10px',
          borderBottom: '1px solid #1A1A1A',
        }}>
          <span style={{ fontFamily: SANS, fontSize: 13, fontWeight: 700, color: '#fff', letterSpacing: '0.01em' }}>
            SPREAD EVENTS
          </span>
          <span style={{
            fontFamily: MONO, fontSize: 11, background: '#111', color: '#888',
            borderRadius: 3, padding: '1px 7px', border: '1px solid #1A1A1A',
          }}>
            {SPREAD_EVENTS.length} events
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#000', borderBottom: '1px solid #1A1A1A' }}>
                {['TIME DETECTED', 'MARKET PAIR', 'PEAK SPREAD', 'DURATION OPEN', 'EST. PROFIT', 'STATUS'].map((col) => (
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
              {SPREAD_EVENTS.map((ev, i) => {
                const statusColors: Record<string, string> = {
                  CAPTURED: '#00FF88',
                  MISSED:   '#FF3355',
                  OPEN:     '#FFB800',
                }
                const statusBgs: Record<string, string> = {
                  CAPTURED: 'rgba(0,255,136,0.08)',
                  MISSED:   'rgba(255,51,85,0.08)',
                  OPEN:     'rgba(255,184,0,0.08)',
                }
                const sc = statusColors[ev.status] ?? '#fff'
                const sb = statusBgs[ev.status] ?? 'transparent'
                const profitColor = ev.estProfit.startsWith('-') ? '#FF3355' : ev.estProfit === '—' ? '#444' : '#00FF88'
                return (
                  <tr
                    key={i}
                    className="row-enter"
                    style={{
                      animationDelay: `${i * 25}ms`,
                      borderBottom: '1px solid #111',
                      transition: 'background 0.12s',
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = '#0D0D0D' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'transparent' }}
                  >
                    <td style={{ fontFamily: MONO, fontSize: 11, color: '#666', padding: '9px 16px', whiteSpace: 'nowrap' }}>
                      {ev.time}
                    </td>
                    <td style={{ fontFamily: SANS, fontSize: 13, color: '#CCCCCC', padding: '9px 16px', whiteSpace: 'nowrap' }}>
                      {ev.pair}
                    </td>
                    <td style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, color: '#fff', padding: '9px 16px', fontVariantNumeric: 'tabular-nums' }}>
                      {ev.peakSpread}
                    </td>
                    <td style={{ fontFamily: MONO, fontSize: 11, color: '#888', padding: '9px 16px', fontVariantNumeric: 'tabular-nums' }}>
                      {ev.duration}
                    </td>
                    <td style={{ fontFamily: MONO, fontSize: 12, fontWeight: 700, color: profitColor, padding: '9px 16px', fontVariantNumeric: 'tabular-nums' }}>
                      {ev.estProfit}
                    </td>
                    <td style={{ padding: '9px 16px' }}>
                      <span style={{
                        fontFamily: MONO, fontSize: 9, fontWeight: 600,
                        color: sc, background: sb,
                        border: `1px solid ${sc}22`,
                        borderRadius: 3, padding: '3px 8px', letterSpacing: '0.08em',
                      }}>
                        {ev.status === 'CAPTURED' ? '✓ ' : ev.status === 'MISSED' ? '✕ ' : '◌ '}{ev.status}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
