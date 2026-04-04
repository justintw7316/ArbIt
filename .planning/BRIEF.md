# ARBX — Project Brief

**Project:** ARBX Frontend + FastAPI Backend
**Date:** 2026-03-28

## What we're building

A Bloomberg Terminal-style live arbitrage signal board for prediction markets. The system backend (steps 1–2: scraper + vector DB) already exists. This project adds the FastAPI API layer and Next.js 14 frontend that surfaces arbitrage candidates to a human operator.

## Problem it solves

The vector_db pipeline (step 2) detects semantically similar questions priced differently across Polymarket, Kalshi, and Manifold. The output sits in MongoDB as `candidate_pairs`. Right now there's no way to see it. The frontend makes the signal visible and actionable.

## Success criteria

- `/api/candidates`, `/api/questions`, `/api/pipeline-status`, `/api/config` all return correct data from MongoDB
- SIGNALS screen shows split panel: ranked candidate list (left) + detail panel (right), auto-selects first row, filters work, re-fetches every 30s
- MARKETS screen shows 3 columns (Polymarket / Kalshi / Manifold) with question lists and `◆` markers on paired questions
- PIPELINE screen shows 7-step status grid with correct done/active/pending states + log console
- Orange Fire aesthetic throughout — looks like a real trading terminal, not a generic dashboard

## Constraints

- Stack: Next.js 14 App Router, Tailwind CSS, FastAPI, MongoDB (PyMongo)
- No auth, no mobile layout, no charting libraries
- No mock data — all numbers from real MongoDB collections
- Full spec: `docs/superpowers/specs/2026-03-28-arbx-frontend-design.md`

## Out of scope

- Steps 3–7 of the pipeline (LLM verifier, arbitrage calc, timing, simulator)
- Authentication / user accounts
- Deployment / hosting
- Mobile responsive layout
