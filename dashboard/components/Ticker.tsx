'use client'
import { TICKER_ITEMS } from '@/lib/mockData'
import type { MarketTicker } from '@/lib/types'

const MONO = 'JetBrains Mono, monospace'
const SANS = 'Inter, sans-serif'

function TickerItem({ item }: { item: MarketTicker }) {
  const isUp = item.change >= 0
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '0 18px',
      borderRight: '1px solid #1A1A1A',
      flexShrink: 0,
      height: '100%',
    }}>
      <span style={{
        fontFamily: SANS,
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: '0.06em',
        padding: '1px 6px',
        borderRadius: 3,
        background: item.platform === 'POLY' ? 'rgba(123,63,228,0.15)' : 'rgba(0,102,255,0.15)',
        color: item.platform === 'POLY' ? '#7B3FE4' : '#0066FF',
        flexShrink: 0,
      }}>
        {item.platform}
      </span>
      <span style={{
        fontFamily: MONO,
        fontSize: 12,
        fontWeight: 500,
        color: '#666',
        whiteSpace: 'nowrap',
        maxWidth: 180,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}>
        {item.name}
      </span>
      <span style={{
        fontFamily: MONO,
        fontSize: 12,
        fontWeight: 500,
        color: '#fff',
        fontVariantNumeric: 'tabular-nums',
        flexShrink: 0,
      }}>
        {item.price.toFixed(2)}
      </span>
      <span style={{
        fontFamily: MONO,
        fontSize: 12,
        fontWeight: 500,
        color: isUp ? '#00FF88' : '#FF3355',
        fontVariantNumeric: 'tabular-nums',
        flexShrink: 0,
      }}>
        {isUp ? '+' : ''}{item.change.toFixed(1)}%
      </span>
    </div>
  )
}

export default function Ticker() {
  const allItems = [...TICKER_ITEMS, ...TICKER_ITEMS]

  return (
    <div style={{
      height: 36,
      background: '#000',
      borderBottom: '1px solid #1A1A1A',
      display: 'flex',
      alignItems: 'stretch',
      overflow: 'hidden',
      flexShrink: 0,
    }}>
      {/* Label */}
      <div style={{
        display: 'flex', alignItems: 'center',
        padding: '0 14px',
        borderRight: '1px solid #1A1A1A',
        flexShrink: 0,
        gap: 7,
      }}>
        <span className="live-dot" />
        <span style={{
          fontFamily: SANS,
          fontSize: 12,
          fontWeight: 700,
          color: '#00FF88',
          letterSpacing: '0.12em',
        }}>
          LIVE
        </span>
      </div>

      {/* Scrolling feed */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        {/* Fade masks */}
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0, width: 32, zIndex: 2,
          background: 'linear-gradient(to right, #000, transparent)',
          pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute', right: 0, top: 0, bottom: 0, width: 32, zIndex: 2,
          background: 'linear-gradient(to left, #000, transparent)',
          pointerEvents: 'none',
        }} />
        <div style={{ display: 'flex', alignItems: 'stretch', height: '100%' }} className="ticker-track">
          {allItems.map((item, i) => (
            <TickerItem key={i} item={item} />
          ))}
        </div>
      </div>
    </div>
  )
}
