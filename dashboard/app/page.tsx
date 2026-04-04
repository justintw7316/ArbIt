'use client'
import { useState, useEffect } from 'react'
import dynamic from 'next/dynamic'
import Ticker from '@/components/Ticker'
import Sidebar from '@/components/Sidebar'
import OpportunityFeed from '@/components/OpportunityFeed'
import MatchesExplorer from '@/components/MatchesExplorer'
import ExecutionLog from '@/components/ExecutionLog'
import { OPPORTUNITIES } from '@/lib/mockData'

const SpreadHistory = dynamic(() => import('@/components/SpreadHistory'), { ssr: false })

type Tab = 'feed' | 'matches' | 'execution' | 'spread'

const TABS: { id: Tab; label: string }[] = [
  { id: 'feed',      label: 'Opportunity Feed' },
  { id: 'matches',   label: 'Matches Explorer' },
  { id: 'execution', label: 'Execution Log' },
  { id: 'spread',    label: 'Spread History' },
]

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<Tab>('feed')
  const [countdown, setCountdown] = useState(5)

  const liveCount = OPPORTUNITIES.filter((o) => o.status === 'live').length

  useEffect(() => {
    const t = setInterval(() => setCountdown((c) => (c <= 1 ? 5 : c - 1)), 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#000' }}>
      <Ticker />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar />
        <main style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', borderLeft: '1px solid #1A1A1A' }}>

          {/* Tab bar */}
          <div style={{
            display: 'flex',
            alignItems: 'stretch',
            height: 40,
            borderBottom: '1px solid #1A1A1A',
            background: '#000',
            flexShrink: 0,
          }}>
            {TABS.map((tab) => {
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: 15,
                    fontWeight: isActive ? 600 : 500,
                    letterSpacing: '0.02em',
                    padding: '0 20px',
                    border: 'none',
                    borderBottom: isActive ? '2px solid #00FF88' : '2px solid transparent',
                    background: 'transparent',
                    color: isActive ? '#fff' : '#888',
                    cursor: 'pointer',
                    transition: 'color 0.15s',
                    outline: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    flexShrink: 0,
                  }}
                  onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = '#ccc' }}
                  onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = '#888' }}
                >
                  {tab.label}
                  {tab.id === 'feed' && (
                    <span style={{
                      fontFamily: 'Inter, sans-serif',
                      fontSize: 10,
                      fontWeight: 700,
                      background: '#00FF88',
                      color: '#000',
                      borderRadius: 10,
                      padding: '1px 6px',
                      lineHeight: '14px',
                    }}>
                      {liveCount}
                    </span>
                  )}
                </button>
              )
            })}

            {/* Right side: LIVE + refresh */}
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 16, paddingRight: 20, borderLeft: '1px solid #1A1A1A', paddingLeft: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className="live-dot" />
                <span style={{ fontFamily: 'Inter, sans-serif', fontSize: 10, fontWeight: 700, color: '#00FF88', letterSpacing: '0.08em' }}>LIVE</span>
              </div>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#666', letterSpacing: '0.06em' }}>
                REFRESH {countdown}s
              </span>
            </div>
          </div>

          {/* Content */}
          <div style={{ flex: 1, overflowY: 'auto', background: '#000' }}>
            {activeTab === 'feed'      && <OpportunityFeed />}
            {activeTab === 'matches'   && <MatchesExplorer />}
            {activeTab === 'execution' && <ExecutionLog />}
            {activeTab === 'spread'    && <SpreadHistory />}
          </div>

        </main>
      </div>
    </div>
  )
}
