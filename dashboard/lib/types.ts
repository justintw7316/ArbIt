export interface Opportunity {
  id: string
  polymarket: { question: string; yesPrice: number; noPrice: number; volume: string }
  kalshi: { question: string; yesPrice: number; noPrice: number; volume: string }
  spread: number
  profitMargin: number
  geminiConfidence: number
  geminiReasoning: string
  timestamp: string
  status: 'live' | 'expired' | 'executed'
  arbType: 'YES_YES' | 'YES_NO' | 'NO_YES'
}

export interface Match {
  id: string
  polymarketQuestion: string
  kalshiQuestion: string
  confidence: number
  status: 'LIVE' | 'EXPIRED'
  timestamp: string
  spread: number
  detail?: {
    embedding_similarity: number
    keyword_overlap: number
    temporal_match: boolean
    notes: string
  }
}

export interface Execution {
  id: string
  time: string
  event: string
  polymarketSide: string
  kalshiSide: string
  grossSpread: number
  netPnl: number
  status: 'CONFIRMED' | 'PENDING' | 'FAILED'
  matchId: string
}

export interface SpreadPoint {
  time: string
  polyPrice: number
  kalshiPrice: number
  spread: number
}

export interface MarketTicker {
  name: string
  price: number
  change: number
  platform: 'POLY' | 'KALS'
}
