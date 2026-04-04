import type { Opportunity, Match, Execution, SpreadPoint, MarketTicker } from './types'

export const OPPORTUNITIES: Opportunity[] = [
  {
    id: 'arb-001',
    polymarket: {
      question: 'Will the Federal Reserve cut interest rates in June 2024?',
      yesPrice: 0.67,
      noPrice: 0.33,
      volume: '$2.4M',
    },
    kalshi: {
      question: 'Fed cuts rates at June 2024 FOMC meeting?',
      yesPrice: 0.61,
      noPrice: 0.39,
      volume: '$1.1M',
    },
    spread: 6.0,
    profitMargin: 5.2,
    geminiConfidence: 87,
    geminiReasoning:
      'Strong semantic alignment confirmed between both questions — both reference the June 2024 FOMC decision window. The 6pp spread between Polymarket (67%) and Kalshi (61%) creates a clear YES_YES arbitrage: buy YES on Kalshi at 0.61 and sell YES on Polymarket at 0.67. After estimated fees of ~0.8%, net profit margin stands at 5.2%. CME FedWatch currently prices June cut at 64%, suggesting Kalshi is slightly underpriced.',
    timestamp: '2024-03-28T11:43:22Z',
    status: 'live',
    arbType: 'YES_YES',
  },
  {
    id: 'arb-002',
    polymarket: {
      question: 'Will Bitcoin reach $100,000 by end of 2024?',
      yesPrice: 0.38,
      noPrice: 0.62,
      volume: '$8.7M',
    },
    kalshi: {
      question: 'Bitcoin price exceeds $100K before January 1, 2025?',
      yesPrice: 0.31,
      noPrice: 0.69,
      volume: '$3.2M',
    },
    spread: 7.0,
    profitMargin: 6.1,
    geminiConfidence: 82,
    geminiReasoning:
      'Both markets resolve identically on BTC reaching $100K before year-end 2024. Polymarket prices this at 38% YES while Kalshi sits at 31% YES — a 7pp gap that exceeds typical fee drag. BUY YES on Kalshi at 0.31 and SELL YES (or equivalently BUY NO on Polymarket) to lock in the spread. Post-halving momentum narratives are stronger on Polymarket, explaining its premium. Embedding similarity score 0.94.',
    timestamp: '2024-03-28T11:38:55Z',
    status: 'live',
    arbType: 'YES_YES',
  },
  {
    id: 'arb-003',
    polymarket: {
      question: 'Will Joe Biden win the 2024 US Presidential Election?',
      yesPrice: 0.44,
      noPrice: 0.56,
      volume: '$15.3M',
    },
    kalshi: {
      question: 'Biden wins the 2024 presidential election?',
      yesPrice: 0.37,
      noPrice: 0.63,
      volume: '$4.8M',
    },
    spread: 7.0,
    profitMargin: 6.4,
    geminiConfidence: 91,
    geminiReasoning:
      'Near-perfect question match on Biden 2024 presidential win. The 7pp disparity (Poly 44% vs Kalshi 37%) is anomalously large for a high-liquidity political market. Liquidity conditions favor execution: both books have >$500K near the spread. BUY YES Kalshi 0.37 + SELL YES Polymarket 0.44. Regulatory arbitrage may explain the persistent Kalshi discount — US-only trading restrictions limit Kalshi liquidity.',
    timestamp: '2024-03-28T11:31:07Z',
    status: 'live',
    arbType: 'YES_YES',
  },
  {
    id: 'arb-004',
    polymarket: {
      question: 'Will SpaceX Starship reach orbit in 2024?',
      yesPrice: 0.72,
      noPrice: 0.28,
      volume: '$1.8M',
    },
    kalshi: {
      question: 'SpaceX Starship completes orbital flight in 2024?',
      yesPrice: 0.65,
      noPrice: 0.35,
      volume: '$620K',
    },
    spread: 7.0,
    profitMargin: 6.8,
    geminiConfidence: 94,
    geminiReasoning:
      'Highest confidence arbitrage in current scan. Both questions resolve on Starship orbital flight in 2024 — temporal and semantic match is exact. 7pp spread with 94% embedding similarity. BUY YES Kalshi 0.65 + SELL YES Polymarket 0.72. Polymarket skews higher due to international retail trader optimism following the March test flight. Kalshi institutional traders have priced in regulatory delays. Net margin 6.8% after 0.2% round-trip fees.',
    timestamp: '2024-03-28T11:28:44Z',
    status: 'live',
    arbType: 'YES_YES',
  },
  {
    id: 'arb-005',
    polymarket: {
      question: 'Will Apple Vision Pro sell more than 500,000 units in 2024?',
      yesPrice: 0.28,
      noPrice: 0.72,
      volume: '$980K',
    },
    kalshi: {
      question: 'Apple Vision Pro 2024 sales exceed 500K units?',
      yesPrice: 0.35,
      noPrice: 0.65,
      volume: '$340K',
    },
    spread: 7.0,
    profitMargin: 5.9,
    geminiConfidence: 79,
    geminiReasoning:
      'Inverted spread detected: Polymarket prices Vision Pro >500K at 28% while Kalshi prices it at 35%. This YES_NO structure means BUY YES Kalshi 0.35 + BUY NO Polymarket 0.28 (equivalent to SELL YES at 0.72). Combined outlay 0.63, guaranteed return 1.00 if exactly one resolves YES. Lower confidence due to ambiguous sales counting methodology between platforms. Fee-adjusted margin 5.9%.',
    timestamp: '2024-03-28T11:22:18Z',
    status: 'live',
    arbType: 'YES_NO',
  },
  {
    id: 'arb-006',
    polymarket: {
      question: 'Will Democrats retain the Senate majority after 2024 elections?',
      yesPrice: 0.31,
      noPrice: 0.69,
      volume: '$3.1M',
    },
    kalshi: {
      question: 'Democrats keep Senate control in 2024 midterms?',
      yesPrice: 0.29,
      noPrice: 0.71,
      volume: '$1.4M',
    },
    spread: 2.0,
    profitMargin: 1.8,
    geminiConfidence: 68,
    geminiReasoning:
      'Marginal spread of 2pp — below typical execution threshold. Semantic match is strong (0.91 similarity) but the spread barely covers round-trip fees estimated at 0.8-1.2%. Market consensus is tightly aligned here, suggesting efficient pricing. Only viable with zero-fee execution routes. Flagging for monitoring — spread may widen following polling data releases or candidate announcements.',
    timestamp: '2024-03-28T11:15:33Z',
    status: 'live',
    arbType: 'YES_YES',
  },
]

export const MATCHES: Match[] = [
  {
    id: 'mtch-001',
    polymarketQuestion: 'Will the Federal Reserve cut interest rates in June 2024?',
    kalshiQuestion: 'Fed cuts rates at June 2024 FOMC meeting?',
    confidence: 97,
    status: 'LIVE',
    timestamp: '2024-03-28T11:43:00Z',
    spread: 6.0,
    detail: {
      embedding_similarity: 0.97,
      keyword_overlap: 0.89,
      temporal_match: true,
      notes: 'Near-perfect match. Both questions resolve on the June 11-12, 2024 FOMC decision. Semantic vectors cosine distance 0.031.',
    },
  },
  {
    id: 'mtch-002',
    polymarketQuestion: 'Will Bitcoin reach $100,000 by end of 2024?',
    kalshiQuestion: 'Bitcoin price exceeds $100K before January 1, 2025?',
    confidence: 94,
    status: 'LIVE',
    timestamp: '2024-03-28T11:38:00Z',
    spread: 7.0,
    detail: {
      embedding_similarity: 0.94,
      keyword_overlap: 0.82,
      temporal_match: true,
      notes: 'Resolution date alignment confirmed. Minor phrasing difference — "by end of 2024" vs "before January 1, 2025" are functionally identical.',
    },
  },
  {
    id: 'mtch-003',
    polymarketQuestion: 'Will Joe Biden win the 2024 US Presidential Election?',
    kalshiQuestion: 'Biden wins the 2024 presidential election?',
    confidence: 96,
    status: 'LIVE',
    timestamp: '2024-03-28T11:31:00Z',
    spread: 7.0,
    detail: {
      embedding_similarity: 0.96,
      keyword_overlap: 0.91,
      temporal_match: true,
      notes: 'High-confidence match. Both resolve on Nov 5, 2024 election outcome. Volume differential: Polymarket 3.2x higher than Kalshi.',
    },
  },
  {
    id: 'mtch-004',
    polymarketQuestion: 'Will SpaceX Starship reach orbit in 2024?',
    kalshiQuestion: 'SpaceX Starship completes orbital flight in 2024?',
    confidence: 95,
    status: 'LIVE',
    timestamp: '2024-03-28T11:28:00Z',
    spread: 7.0,
    detail: {
      embedding_similarity: 0.95,
      keyword_overlap: 0.88,
      temporal_match: true,
      notes: '"Reach orbit" and "completes orbital flight" carry identical resolution criteria per both platform rule documents reviewed.',
    },
  },
  {
    id: 'mtch-005',
    polymarketQuestion: 'Apple Vision Pro sell more than 500,000 units in 2024?',
    kalshiQuestion: 'Apple Vision Pro 2024 sales exceed 500K units?',
    confidence: 91,
    status: 'LIVE',
    timestamp: '2024-03-28T11:22:00Z',
    spread: 7.0,
    detail: {
      embedding_similarity: 0.91,
      keyword_overlap: 0.85,
      temporal_match: true,
      notes: 'Slight ambiguity: Polymarket may count pre-orders while Kalshi counts shipped units. Risk factor applied (-3% confidence).',
    },
  },
  {
    id: 'mtch-006',
    polymarketQuestion: 'Will Democrats retain the Senate majority after 2024 elections?',
    kalshiQuestion: 'Democrats keep Senate control in 2024 midterms?',
    confidence: 89,
    status: 'LIVE',
    timestamp: '2024-03-28T11:15:00Z',
    spread: 2.0,
    detail: {
      embedding_similarity: 0.89,
      keyword_overlap: 0.78,
      temporal_match: true,
      notes: '"2024 elections" vs "2024 midterms" terminology differs — confirmed same resolution event via rule document cross-reference.',
    },
  },
  {
    id: 'mtch-007',
    polymarketQuestion: 'Will the S&P 500 reach 6000 by end of 2024?',
    kalshiQuestion: 'S&P 500 hits 6,000 before December 31, 2024?',
    confidence: 93,
    status: 'EXPIRED',
    timestamp: '2024-03-27T16:44:00Z',
    spread: 3.5,
    detail: {
      embedding_similarity: 0.93,
      keyword_overlap: 0.86,
      temporal_match: true,
      notes: 'Expired after spread compressed to 0.4pp. Market converged within 18 hours of detection.',
    },
  },
  {
    id: 'mtch-008',
    polymarketQuestion: 'Will Elon Musk remain Twitter/X CEO through 2024?',
    kalshiQuestion: 'Is Elon Musk still CEO of X at year-end 2024?',
    confidence: 88,
    status: 'EXPIRED',
    timestamp: '2024-03-27T14:22:00Z',
    spread: 2.1,
    detail: {
      embedding_similarity: 0.88,
      keyword_overlap: 0.74,
      temporal_match: true,
      notes: 'Spread closed. Both markets priced at ~82% YES after executive announcement. Expired naturally.',
    },
  },
  {
    id: 'mtch-009',
    polymarketQuestion: 'Will GPT-5 be released in 2024?',
    kalshiQuestion: 'OpenAI releases GPT-5 model in calendar year 2024?',
    confidence: 85,
    status: 'LIVE',
    timestamp: '2024-03-28T10:55:00Z',
    spread: 4.2,
    detail: {
      embedding_similarity: 0.85,
      keyword_overlap: 0.79,
      temporal_match: true,
      notes: '"GPT-5 released" interpreted as public API access. Kalshi rules specify "generally available" vs Polymarket "announced". Confidence penalty applied.',
    },
  },
  {
    id: 'mtch-010',
    polymarketQuestion: 'Will there be a US recession in 2024?',
    kalshiQuestion: 'Does the US enter recession in 2024?',
    confidence: 72,
    status: 'LIVE',
    timestamp: '2024-03-28T10:30:00Z',
    spread: 1.8,
    detail: {
      embedding_similarity: 0.72,
      keyword_overlap: 0.68,
      temporal_match: true,
      notes: 'Recession definition differs: Polymarket uses NBER declaration, Kalshi uses two consecutive negative GDP quarters. Material resolution risk. Low confidence warranted.',
    },
  },
  {
    id: 'mtch-011',
    polymarketQuestion: 'Will Ukraine recapture Crimea by end of 2024?',
    kalshiQuestion: 'Ukraine retakes Crimea in 2024?',
    confidence: 92,
    status: 'EXPIRED',
    timestamp: '2024-03-26T09:15:00Z',
    spread: 0.8,
    detail: {
      embedding_similarity: 0.92,
      keyword_overlap: 0.88,
      temporal_match: true,
      notes: 'Spread too narrow for execution after fees. Archived.',
    },
  },
  {
    id: 'mtch-012',
    polymarketQuestion: 'Will the NBA MVP award go to Nikola Jokic in 2024?',
    kalshiQuestion: 'Jokic wins NBA Most Valuable Player award 2023-24 season?',
    confidence: 86,
    status: 'LIVE',
    timestamp: '2024-03-28T09:47:00Z',
    spread: 5.3,
    detail: {
      embedding_similarity: 0.86,
      keyword_overlap: 0.81,
      temporal_match: true,
      notes: 'Season designation phrasing differs slightly. Confirmed same award cycle. Spread of 5.3pp potentially actionable pending volume confirmation.',
    },
  },
]

export const EXECUTIONS: Execution[] = [
  {
    id: 'exec-001',
    time: '11:43:07',
    event: 'BUY YES Kalshi + SELL YES Polymarket — Fed Rate Cut June',
    polymarketSide: 'SELL YES @ 0.670',
    kalshiSide: 'BUY YES @ 0.610',
    grossSpread: 6.0,
    netPnl: 847.32,
    status: 'CONFIRMED',
    matchId: 'mtch-001',
  },
  {
    id: 'exec-002',
    time: '11:38:22',
    event: 'BUY YES Kalshi + SELL YES Polymarket — BTC $100K EOY',
    polymarketSide: 'SELL YES @ 0.380',
    kalshiSide: 'BUY YES @ 0.310',
    grossSpread: 7.0,
    netPnl: 612.50,
    status: 'CONFIRMED',
    matchId: 'mtch-002',
  },
  {
    id: 'exec-003',
    time: '11:31:44',
    event: 'BUY YES Kalshi + SELL YES Polymarket — Biden 2024 Win',
    polymarketSide: 'SELL YES @ 0.440',
    kalshiSide: 'BUY YES @ 0.370',
    grossSpread: 7.0,
    netPnl: 743.18,
    status: 'CONFIRMED',
    matchId: 'mtch-003',
  },
  {
    id: 'exec-004',
    time: '11:28:59',
    event: 'BUY YES Kalshi + SELL YES Polymarket — Starship Orbital',
    polymarketSide: 'SELL YES @ 0.720',
    kalshiSide: 'BUY YES @ 0.650',
    grossSpread: 7.0,
    netPnl: 521.75,
    status: 'PENDING',
    matchId: 'mtch-004',
  },
  {
    id: 'exec-005',
    time: '11:22:11',
    event: 'BUY YES Kalshi + BUY NO Polymarket — Apple Vision Pro 500K',
    polymarketSide: 'BUY NO @ 0.720',
    kalshiSide: 'BUY YES @ 0.350',
    grossSpread: 5.9,
    netPnl: 389.40,
    status: 'CONFIRMED',
    matchId: 'mtch-005',
  },
  {
    id: 'exec-006',
    time: '11:15:03',
    event: 'BUY YES Kalshi + SELL YES Polymarket — Senate Dems Majority',
    polymarketSide: 'SELL YES @ 0.310',
    kalshiSide: 'BUY YES @ 0.290',
    grossSpread: 2.0,
    netPnl: -12.30,
    status: 'FAILED',
    matchId: 'mtch-006',
  },
  {
    id: 'exec-007',
    time: '10:58:34',
    event: 'BUY YES Kalshi + SELL YES Polymarket — GPT-5 Release 2024',
    polymarketSide: 'SELL YES @ 0.510',
    kalshiSide: 'BUY YES @ 0.468',
    grossSpread: 4.2,
    netPnl: 298.65,
    status: 'CONFIRMED',
    matchId: 'mtch-009',
  },
  {
    id: 'exec-008',
    time: '10:47:21',
    event: 'BUY YES Kalshi + SELL YES Polymarket — S&P 500 6K EOY',
    polymarketSide: 'SELL YES @ 0.620',
    kalshiSide: 'BUY YES @ 0.585',
    grossSpread: 3.5,
    netPnl: 215.90,
    status: 'CONFIRMED',
    matchId: 'mtch-007',
  },
  {
    id: 'exec-009',
    time: '10:33:55',
    event: 'BUY YES Kalshi + SELL YES Polymarket — NBA MVP Jokic',
    polymarketSide: 'SELL YES @ 0.680',
    kalshiSide: 'BUY YES @ 0.627',
    grossSpread: 5.3,
    netPnl: 467.22,
    status: 'CONFIRMED',
    matchId: 'mtch-012',
  },
  {
    id: 'exec-010',
    time: '10:21:08',
    event: 'BUY YES Kalshi + SELL YES Polymarket — Fed Rate Cut June [RETRY]',
    polymarketSide: 'SELL YES @ 0.658',
    kalshiSide: 'BUY YES @ 0.602',
    grossSpread: 5.6,
    netPnl: 334.88,
    status: 'PENDING',
    matchId: 'mtch-001',
  },
  {
    id: 'exec-011',
    time: '10:09:47',
    event: 'BUY YES Kalshi + SELL YES Polymarket — Biden Win [PARTIAL FILL]',
    polymarketSide: 'SELL YES @ 0.435',
    kalshiSide: 'BUY YES @ 0.368',
    grossSpread: 6.7,
    netPnl: 512.44,
    status: 'CONFIRMED',
    matchId: 'mtch-003',
  },
  {
    id: 'exec-012',
    time: '09:54:30',
    event: 'BUY NO Polymarket + SELL NO Kalshi — BTC $100K Hedged',
    polymarketSide: 'BUY NO @ 0.620',
    kalshiSide: 'SELL NO @ 0.690',
    grossSpread: 7.0,
    netPnl: -8.75,
    status: 'FAILED',
    matchId: 'mtch-002',
  },
  {
    id: 'exec-013',
    time: '09:41:16',
    event: 'BUY YES Kalshi + SELL YES Polymarket — Starship Orbital [INIT]',
    polymarketSide: 'SELL YES @ 0.710',
    kalshiSide: 'BUY YES @ 0.641',
    grossSpread: 6.9,
    netPnl: 388.15,
    status: 'CONFIRMED',
    matchId: 'mtch-004',
  },
  {
    id: 'exec-014',
    time: '09:28:03',
    event: 'BUY YES Kalshi + SELL YES Polymarket — Senate Dems [MONITOR]',
    polymarketSide: 'SELL YES @ 0.318',
    kalshiSide: 'BUY YES @ 0.295',
    grossSpread: 2.3,
    netPnl: 142.60,
    status: 'PENDING',
    matchId: 'mtch-006',
  },
]

// 48 data points over 24 hours for spread history
function generateSpreadHistory(): SpreadPoint[] {
  const points: SpreadPoint[] = []
  let polyPrice = 0.64
  let kalshiPrice = 0.58

  for (let i = 0; i < 48; i++) {
    const hour = Math.floor(i / 2)
    const min = i % 2 === 0 ? '00' : '30'
    const timeLabel = `${String(hour).padStart(2, '0')}:${min}`

    // Small random walks with mean reversion
    const polyDelta = (Math.random() - 0.5) * 0.018 + (0.63 - polyPrice) * 0.05
    const kalshiDelta = (Math.random() - 0.5) * 0.014 + (0.60 - kalshiPrice) * 0.04

    polyPrice = Math.max(0.35, Math.min(0.85, polyPrice + polyDelta))
    kalshiPrice = Math.max(0.30, Math.min(0.80, kalshiPrice + kalshiDelta))

    // Occasional spread spikes
    if (i % 11 === 0) {
      kalshiPrice -= 0.025
    }
    if (i % 17 === 0) {
      polyPrice += 0.018
    }

    points.push({
      time: timeLabel,
      polyPrice: parseFloat(polyPrice.toFixed(3)),
      kalshiPrice: parseFloat(kalshiPrice.toFixed(3)),
      spread: parseFloat(Math.abs(polyPrice - kalshiPrice).toFixed(3)),
    })
  }

  return points
}

export const SPREAD_HISTORY: SpreadPoint[] = generateSpreadHistory()

export const TICKER_ITEMS: MarketTicker[] = [
  { name: 'Fed rate cut June 2024', price: 0.67, change: 2.1, platform: 'POLY' },
  { name: 'BTC >$100K by EOY', price: 0.38, change: -1.4, platform: 'POLY' },
  { name: 'Biden wins 2024 election', price: 0.44, change: 0.8, platform: 'POLY' },
  { name: 'Starship orbital 2024', price: 0.72, change: 3.2, platform: 'POLY' },
  { name: 'Apple VisionPro >500K units', price: 0.28, change: -0.5, platform: 'POLY' },
  { name: 'Dems keep Senate 2024', price: 0.31, change: -1.1, platform: 'POLY' },
  { name: 'S&P 500 hits 6000', price: 0.62, change: 1.7, platform: 'POLY' },
  { name: 'GPT-5 released 2024', price: 0.51, change: 0.3, platform: 'POLY' },
  { name: 'Fed rate cut June 2024', price: 0.61, change: 1.8, platform: 'KALS' },
  { name: 'BTC >$100K by EOY', price: 0.31, change: -1.2, platform: 'KALS' },
  { name: 'Biden wins 2024', price: 0.37, change: 0.4, platform: 'KALS' },
  { name: 'Starship orbital 2024', price: 0.65, change: 2.9, platform: 'KALS' },
  { name: 'Apple VisionPro >500K', price: 0.35, change: -0.3, platform: 'KALS' },
  { name: 'Dems keep Senate', price: 0.29, change: -0.9, platform: 'KALS' },
  { name: 'S&P 500 hits 6000', price: 0.585, change: 1.4, platform: 'KALS' },
  { name: 'Jokic wins NBA MVP', price: 0.627, change: 2.1, platform: 'KALS' },
  { name: 'Ukraine retakes Crimea 2024', price: 0.08, change: 0.2, platform: 'POLY' },
  { name: 'Elon Musk remains X CEO', price: 0.81, change: -0.6, platform: 'KALS' },
  { name: 'US recession declared 2024', price: 0.14, change: -0.3, platform: 'POLY' },
  { name: 'OpenAI releases GPT-5', price: 0.468, change: 0.5, platform: 'KALS' },
]
