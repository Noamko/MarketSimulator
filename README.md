# MarketSimulator

A small local paper-trading simulator for US equities. Live prices stream in from Finnhub over WebSocket, you place fake buy/sell orders, and a SQLite file keeps your account so it survives restarts.

**No real money. Localhost only.** This is a learning project.

---

## How it works

```
Finnhub WS  ─►  Python backend (FastAPI)  ─►  React frontend
                  └─ SQLite (cash + lots + trades)
```

- The backend holds **one** WebSocket to Finnhub and fans the price ticks out to every connected browser tab via its own `/ws` endpoint.
- Buys insert a FIFO **lot** with the trade's execution price as cost basis.
- Sells walk lots oldest-first and compute realized P&L per share consumed.
- Money is stored as integer cents to avoid float drift.

## Data sources (all free)

| API | Used for | Auth | Cost | Notes |
|-----|----------|------|------|-------|
| [Finnhub](https://finnhub.io) — WebSocket `wss://ws.finnhub.io` | Real-time trade ticks (the "Sec" timeframe) | Free API key | $0 | US stocks only. Ticks flow only during US market hours (Mon–Fri 09:30–16:00 ET). ~50 concurrent symbol subscriptions, 60 REST calls/min. |
| [Finnhub](https://finnhub.io) — REST `/quote` | Last-close fallback when the market is closed | Free API key | $0 | Same key/limits as above. |
| [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance) | Historical bars for the Min, Hour, Day, Week, Month, Year, 2Y, 5Y, 10Y timeframes | None | $0 | Unofficial Python library that scrapes Yahoo's public endpoints. No API key, no signup. Soft rate-limited; we cache responses server-side (15s–6h depending on range). Yahoo can change endpoints and break this any time. |

We do **not** use any paid data plan. Finnhub's historical-candles endpoint moved to a paid tier a few years ago — that's why we use yfinance for history instead.

## Prerequisites

- Python 3.11+
- Node.js 18+
- A free Finnhub API key — sign up at https://finnhub.io/register and copy the key from your dashboard.

## Setup

```bash
# 1. Configure your API key
cp .env.example .env
# then edit .env and paste your FINNHUB_API_KEY

# 2. Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Frontend
cd ../frontend
npm install
```

## Run

Two terminals:

```bash
# Terminal 1 — backend on :8000
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2 — frontend on :5173
cd frontend
npm run dev
```

Open http://localhost:5173.

## Things to know about the data

- **Finnhub's free tier only streams trade ticks during US market hours** — Mon–Fri, 09:30–16:00 ET. Outside that window the WebSocket connects but emits nothing. The UI shows `Market closed` and falls back to a REST quote (last close) so prices aren't empty.
- US stocks only (NASDAQ/NYSE). Bare tickers like `AAPL`, `MSFT`, `SPY`.
- ~50 symbols can be watched concurrently on the free plan; the backend ref-counts subscriptions so unwatched symbols are automatically unsubscribed upstream.

## Reset your account

Stop the backend, delete the SQLite file, and start again:

```bash
rm backend/data/market_sim.db
```

The starting cash balance can be changed in `.env` (`STARTING_CASH_CENTS`, in cents).

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

Covers buy, partial sell, FIFO across multiple lots, full liquidation, insufficient funds, and insufficient shares.

## Project layout

```
backend/                 FastAPI + SQLite
  app/
    main.py              lifespan starts PriceHub
    price_hub.py         upstream Finnhub WS + asyncio fan-out
    trading.py           buy/sell with FIFO
    portfolio.py         derived position + P&L snapshot
    schema.sql           SQLite schema
    history.py           yfinance-backed historical candles + tick buffer
    routes/              /api/portfolio, /api/trades, /api/quote, /api/history, /ws
  tests/test_trading.py
frontend/                React + Vite + lightweight-charts
  src/
    App.tsx
    hooks/useMarketSocket.ts
    components/
```
