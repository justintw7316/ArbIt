'use client'
import { OPPORTUNITIES } from '@/lib/mockData'
import OpportunityCard from './OpportunityCard'

const SANS = 'Inter, sans-serif'
const MONO = 'JetBrains Mono, monospace'

export default function OpportunityFeed() {
  const liveOpps = OPPORTUNITIES.filter((o) => o.status === 'live')

  return (
    <div>
      {/* Section header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '14px 20px 12px',
        borderBottom: '1px solid #1A1A1A',
        background: '#000',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <span style={{ fontFamily: SANS, fontSize: 13, fontWeight: 700, color: '#fff', letterSpacing: '0.01em' }}>
          LIVE OPPORTUNITIES
        </span>
        <span style={{
          fontFamily: MONO, fontSize: 11,
          background: '#00FF88', color: '#000',
          borderRadius: 3, padding: '1px 7px', fontWeight: 700,
        }}>
          {liveOpps.length}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#00FF88' }} />
          <span style={{ fontFamily: MONO, fontSize: 10, color: '#666', letterSpacing: '0.1em' }}>
            AUTO-REFRESH 5s
          </span>
        </div>
      </div>

      {/* Cards */}
      {liveOpps.length === 0 ? (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          height: 200,
          fontFamily: MONO, fontSize: 11, color: '#666', letterSpacing: '0.1em',
        }}>
          SCANNING FOR OPPORTUNITIES...
        </div>
      ) : (
        <div>
          {liveOpps.map((opp, i) => (
            <OpportunityCard key={opp.id} opportunity={opp} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}
