'use client'
import { useState } from 'react'
import type { Opportunity } from '@/lib/types'

const MONO = 'JetBrains Mono, monospace'
const SANS = 'Inter, sans-serif'

interface Props { opportunity: Opportunity; index: number }

export default function OpportunityCard({ opportunity }: Props) {
  const [reasoningOpen, setReasoningOpen] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [execHovered, setExecHovered] = useState(false)

  const { polymarket, kalshi, spread, profitMargin, geminiConfidence, geminiReasoning, timestamp, arbType, id } = opportunity

  const timeStr = new Date(timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

  const confColor = geminiConfidence > 80 ? '#00FF88' : geminiConfidence > 60 ? '#FFB800' : '#FF3355'

  const arbLeft  = arbType === 'YES_YES' ? 'BUY YES'  : 'BUY NO'
  const arbRight = arbType === 'YES_YES' ? 'SELL YES' : 'BUY YES'

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? '#111' : '#0A0A0A',
        borderLeft: '2px solid #00FF88',
        borderBottom: '1px solid #1A1A1A',
        transition: 'background 0.15s',
      }}
    >
      {/* Top info strip */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '6px 16px',
        borderBottom: '1px solid #1A1A1A',
        background: '#000',
      }}>
        <span style={{
          fontFamily: MONO, fontSize: 10, color: '#888',
          background: '#111', padding: '1px 6px', borderRadius: 2,
        }}>
          {id.toUpperCase()}
        </span>
        <span style={{ fontFamily: MONO, fontSize: 10, color: '#666', letterSpacing: '0.06em' }}>
          {arbType}
        </span>
        <span style={{ fontFamily: MONO, fontSize: 10, color: '#666', marginLeft: 'auto' }}>
          {timeStr}
        </span>
      </div>

      {/* Main body — 4 columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px 1fr 150px' }}>

        {/* Polymarket */}
        <div style={{ padding: '14px 16px', borderRight: '1px solid #1A1A1A' }}>
          <span style={{
            display: 'inline-block', marginBottom: 8,
            fontFamily: SANS, fontSize: 11, fontWeight: 600, letterSpacing: '0.08em',
            padding: '2px 7px', borderRadius: 3,
            background: 'rgba(123,63,228,0.12)', color: '#7B3FE4',
          }}>
            POLYMARKET
          </span>
          <p style={{
            fontFamily: SANS, fontSize: 15, fontWeight: 500, color: '#FFFFFF',
            lineHeight: 1.4, marginBottom: 10,
            display: '-webkit-box', WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical' as const, overflow: 'hidden',
          }}>
            {polymarket.question}
          </p>
          <div style={{ display: 'flex', gap: 18, marginBottom: 6 }}>
            <div>
              <div style={{ fontFamily: MONO, fontSize: 22, fontWeight: 700, color: '#00FF88', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
                {polymarket.yesPrice.toFixed(2)}
              </div>
              <div style={{ fontFamily: SANS, fontSize: 9, fontWeight: 600, color: '#888', letterSpacing: '0.1em', marginTop: 3 }}>YES</div>
            </div>
            <div>
              <div style={{ fontFamily: MONO, fontSize: 22, fontWeight: 700, color: '#FF3355', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
                {polymarket.noPrice.toFixed(2)}
              </div>
              <div style={{ fontFamily: SANS, fontSize: 9, fontWeight: 600, color: '#888', letterSpacing: '0.1em', marginTop: 3 }}>NO</div>
            </div>
          </div>
          <div style={{ fontFamily: MONO, fontSize: 10, color: '#666' }}>VOL {polymarket.volume}</div>
        </div>

        {/* Center divider */}
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          borderRight: '1px solid #1A1A1A', padding: '14px 8px', gap: 4,
        }}>
          <span style={{ fontFamily: SANS, fontSize: 9, fontWeight: 600, color: '#888', letterSpacing: '0.1em' }}>{arbLeft}</span>
          <div style={{
            width: 28, height: 28, borderRadius: 4,
            border: '1px solid #1A1A1A',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#00FF88', fontSize: 14,
          }}>⇄</div>
          <span style={{ fontFamily: SANS, fontSize: 9, fontWeight: 600, color: '#888', letterSpacing: '0.1em' }}>{arbRight}</span>
        </div>

        {/* Kalshi */}
        <div style={{ padding: '14px 16px', borderRight: '1px solid #1A1A1A' }}>
          <span style={{
            display: 'inline-block', marginBottom: 8,
            fontFamily: SANS, fontSize: 11, fontWeight: 600, letterSpacing: '0.08em',
            padding: '2px 7px', borderRadius: 3,
            background: 'rgba(0,102,255,0.12)', color: '#0066FF',
          }}>
            KALSHI
          </span>
          <p style={{
            fontFamily: SANS, fontSize: 15, fontWeight: 500, color: '#FFFFFF',
            lineHeight: 1.4, marginBottom: 10,
            display: '-webkit-box', WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical' as const, overflow: 'hidden',
          }}>
            {kalshi.question}
          </p>
          <div style={{ display: 'flex', gap: 18, marginBottom: 6 }}>
            <div>
              <div style={{ fontFamily: MONO, fontSize: 22, fontWeight: 700, color: '#00FF88', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
                {kalshi.yesPrice.toFixed(2)}
              </div>
              <div style={{ fontFamily: SANS, fontSize: 9, fontWeight: 600, color: '#888', letterSpacing: '0.1em', marginTop: 3 }}>YES</div>
            </div>
            <div>
              <div style={{ fontFamily: MONO, fontSize: 22, fontWeight: 700, color: '#FF3355', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
                {kalshi.noPrice.toFixed(2)}
              </div>
              <div style={{ fontFamily: SANS, fontSize: 9, fontWeight: 600, color: '#888', letterSpacing: '0.1em', marginTop: 3 }}>NO</div>
            </div>
          </div>
          <div style={{ fontFamily: MONO, fontSize: 10, color: '#666' }}>VOL {kalshi.volume}</div>
        </div>

        {/* Spread hero */}
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: '14px 16px', gap: 4,
        }}>
          <div style={{
            fontFamily: MONO, fontSize: 42, fontWeight: 800,
            color: '#00FF88', lineHeight: 1,
            letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums',
          }}>
            +{spread.toFixed(1)}%
          </div>
          <div style={{ fontFamily: SANS, fontSize: 11, fontWeight: 500, color: '#666', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            NET {profitMargin.toFixed(1)}% MARGIN
          </div>
        </div>
      </div>

      {/* Confidence bar + execute footer */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '8px 16px',
        borderTop: '1px solid #1A1A1A',
      }}>
        <span style={{ fontFamily: SANS, fontSize: 12, fontWeight: 600, color: '#888', letterSpacing: '0.1em', flexShrink: 0 }}>
          AI CONFIDENCE
        </span>
        <div style={{ flex: 1, height: 2, background: '#1A1A1A' }}>
          <div
            className="confidence-bar"
            style={{ height: '100%', width: `${geminiConfidence}%`, background: confColor }}
          />
        </div>
        <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, color: confColor, flexShrink: 0, fontVariantNumeric: 'tabular-nums', letterSpacing: '0.1em' }}>
          {geminiConfidence}%
        </span>

        <button
          onClick={() => setReasoningOpen(!reasoningOpen)}
          style={{
            fontFamily: SANS, fontSize: 11, color: '#666',
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '0 8px', flexShrink: 0, letterSpacing: '0.06em',
            transition: 'color 0.15s',
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = '#aaa' }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = '#666' }}
        >
          {reasoningOpen ? '▲' : '▼'} REASONING
        </button>

        <button
          onMouseEnter={() => setExecHovered(true)}
          onMouseLeave={() => setExecHovered(false)}
          style={{
            fontFamily: SANS, fontSize: 13, fontWeight: 600,
            letterSpacing: '0.08em',
            padding: '5px 18px',
            borderRadius: 20,
            border: `1px solid ${execHovered ? '#00FF88' : '#333'}`,
            background: execHovered ? '#00FF88' : 'transparent',
            color: execHovered ? '#000' : '#fff',
            cursor: 'pointer',
            transition: 'all 0.2s',
            flexShrink: 0,
          }}
        >
          EXECUTE
        </button>
      </div>

      {/* Reasoning panel */}
      {reasoningOpen && (
        <div style={{
          padding: '12px 16px 14px',
          borderTop: '1px solid #1A1A1A',
          background: '#050505',
        }}>
          <p style={{
            fontFamily: MONO, fontSize: 12, color: '#888',
            lineHeight: 1.7, margin: 0,
          }}>
            {geminiReasoning}
          </p>
        </div>
      )}
    </div>
  )
}
