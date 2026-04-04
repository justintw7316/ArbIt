'use client'
import { useState } from 'react'
import { MATCHES } from '@/lib/mockData'
import type { Match } from '@/lib/types'

const MONO = 'JetBrains Mono, monospace'
const SANS = 'Inter, sans-serif'

function ConfidenceBadge({ value }: { value: number }) {
  const color = value > 85 ? '#00FF88' : value > 70 ? '#FFB800' : '#FF3355'
  return (
    <span style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600, color, fontVariantNumeric: 'tabular-nums' }}>
      {value}%
    </span>
  )
}

function StatusPill({ status }: { status: Match['status'] }) {
  if (status === 'LIVE') {
    return (
      <span style={{
        fontFamily: MONO, fontSize: 10, fontWeight: 600,
        color: '#00FF88', background: 'rgba(0,255,136,0.08)',
        border: '1px solid rgba(0,255,136,0.25)',
        padding: '3px 8px', borderRadius: 3, letterSpacing: '0.08em',
      }}>
        ● LIVE
      </span>
    )
  }
  return (
    <span style={{
      fontFamily: MONO, fontSize: 10, fontWeight: 600,
      color: '#666', border: '1px solid #1A1A1A',
      padding: '3px 8px', borderRadius: 3, letterSpacing: '0.08em',
    }}>
      ○ EXPIRED
    </span>
  )
}

const COLS = ['ID', 'POLYMARKET QUESTION', 'KALSHI QUESTION', 'CONFIDENCE', 'STATUS', 'SPREAD']

export default function MatchesExplorer() {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const toggle = (id: string) => setExpandedId((prev) => (prev === id ? null : id))

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
          MATCHES EXPLORER
        </span>
        <span style={{
          fontFamily: MONO, fontSize: 11,
          background: '#111', color: '#888',
          borderRadius: 3, padding: '1px 7px',
          border: '1px solid #1A1A1A',
        }}>
          {MATCHES.length} matches
        </span>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: 88 }} />
            <col style={{ width: '28%' }} />
            <col style={{ width: '28%' }} />
            <col style={{ width: 100 }} />
            <col style={{ width: 90 }} />
            <col style={{ width: 80 }} />
          </colgroup>
          <thead>
            <tr style={{ background: '#000', borderBottom: '1px solid #1A1A1A' }}>
              {COLS.map((col) => (
                <th key={col} style={{
                  fontFamily: SANS, fontSize: 11, fontWeight: 600,
                  color: '#888', letterSpacing: '0.1em',
                  textAlign: 'left', padding: '9px 16px',
                  textTransform: 'uppercase',
                }}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MATCHES.map((match, i) => (
              <>
                <tr
                  key={match.id}
                  className="row-enter"
                  onClick={() => toggle(match.id)}
                  style={{
                    animationDelay: `${i * 40}ms`,
                    cursor: 'pointer',
                    borderBottom: '1px solid #1A1A1A',
                    transition: 'background 0.12s',
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = '#0D0D0D' }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLTableRowElement).style.background = 'transparent' }}
                >
                  <td style={{ fontFamily: MONO, fontSize: 10, color: '#666', padding: '11px 16px', letterSpacing: '0.06em' }}>
                    {match.id.toUpperCase()}
                  </td>
                  <td style={{ fontFamily: SANS, fontSize: 13, color: '#CCCCCC', padding: '11px 16px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={match.polymarketQuestion}>
                    {match.polymarketQuestion}
                  </td>
                  <td style={{ fontFamily: SANS, fontSize: 13, color: '#CCCCCC', padding: '11px 16px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={match.kalshiQuestion}>
                    {match.kalshiQuestion}
                  </td>
                  <td style={{ padding: '11px 16px' }}>
                    <ConfidenceBadge value={match.confidence} />
                  </td>
                  <td style={{ padding: '11px 16px' }}>
                    <StatusPill status={match.status} />
                  </td>
                  <td style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600, color: '#fff', padding: '11px 16px', fontVariantNumeric: 'tabular-nums' }}>
                    {match.spread.toFixed(1)}pp
                  </td>
                </tr>

                {expandedId === match.id && match.detail && (
                  <tr key={`${match.id}-detail`}>
                    <td
                      colSpan={6}
                      style={{
                        padding: '14px 20px 16px',
                        borderBottom: '1px solid #1A1A1A',
                        borderLeft: '2px solid #00FF88',
                        background: '#050505',
                      }}
                    >
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px 32px', maxWidth: 560 }}>
                        {[
                          { label: 'EMBEDDING SIMILARITY', value: match.detail.embedding_similarity.toFixed(3) },
                          { label: 'KEYWORD OVERLAP',      value: match.detail.keyword_overlap.toFixed(3) },
                          { label: 'TEMPORAL MATCH',       value: match.detail.temporal_match ? 'YES' : 'NO' },
                          { label: 'TIMESTAMP',            value: match.timestamp },
                        ].map(({ label, value }) => (
                          <div key={label}>
                            <div style={{ fontFamily: SANS, fontSize: 10, fontWeight: 600, color: '#888', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4 }}>
                              {label}
                            </div>
                            <div style={{ fontFamily: MONO, fontSize: 13, color: '#00FF88', fontVariantNumeric: 'tabular-nums' }}>
                              {value}
                            </div>
                          </div>
                        ))}
                        <div style={{ gridColumn: '1 / -1' }}>
                          <div style={{ fontFamily: SANS, fontSize: 10, fontWeight: 600, color: '#888', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4 }}>
                            NOTES
                          </div>
                          <div style={{ fontFamily: MONO, fontSize: 12, color: '#888', lineHeight: 1.7 }}>
                            {match.detail.notes}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
