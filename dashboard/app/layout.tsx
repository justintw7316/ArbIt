import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Arbit — Prediction Market Arbitrage',
  description: 'Real-time arbitrage scanner for Polymarket and Kalshi',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
