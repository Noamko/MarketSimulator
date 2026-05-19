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

## Users

There is no password / login. On first launch you'll see a screen with two options:

- **Pick an existing user** — clicking signs you in as that user. Their portfolio, trades, watchlist, etc. are scoped to them.
- **Create a new user** — enter a unique name and a starting cash amount (in dollars). The new user is created on the backend and you're signed in immediately.

The signed-in user's name appears in the header with a **switch** link that takes you back to the login screen. Each user has their own cash balance, positions, trade history, and watchlist (the watchlist is stored locally per user in your browser).

Users live in the `users` table in SQLite. To reset everything, stop the backend and delete `backend/data/market_sim.db` — the next start will boot with no users and the login screen will go straight to "create user".

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

Covers buy, partial sell, FIFO across multiple lots, full liquidation, insufficient funds, and insufficient shares.

## Backend API

All routes are served by the FastAPI app on `:8000`. The frontend dev server proxies `/api/*` and `/ws` so you can also hit them at `:5173`. Interactive Swagger docs: http://localhost:8000/docs.

User-scoped endpoints (marked **U** below) require an `X-User-Id: <id>` request header — the frontend reads the signed-in user from localStorage and sends this on every fetch.

| Method | Path | U | Purpose |
|--------|------|---|---------|
| `GET`  | `/api/health` |   | Liveness + market-open flag. |
| `GET`  | `/api/users`  |   | List all users (`[{id, name, cash_cents, created_at}]`). |
| `POST` | `/api/users`  |   | Create a new user. Body: `{ "name": "noam", "starting_cash_cents": 10000000 }`. 400 if the name is already taken. |
| `GET`  | `/api/portfolio` | ✓ | Current account snapshot for the signed-in user: cash, per-symbol positions with avg cost / market value / unrealized P&L, realized P&L, total equity, and `market_open`. |
| `POST` | `/api/trades` | ✓ | Execute a paper buy or sell at the latest known price. Body: `{ "symbol": "AAPL", "side": "BUY" \| "SELL", "quantity": 10 }`. Returns `{trade_id, price_cents, realized_pnl_cents}` (the last is non-null only for SELLs). 400 on insufficient cash / shares. |
| `GET`  | `/api/trades?limit=N` | ✓ | Trade history for the signed-in user (newest first), capped at `limit` (default 100, max 1000). |
| `GET`  | `/api/quote/{symbol}` |   | Latest price + previous close for a single symbol. Reads the in-memory cache first, falls back to Finnhub REST. |
| `GET`  | `/api/history/{symbol}?range=<label>` |   | Historical bars for the chart. `range` is one of: `Sec`, `Min`, `Hour`, `Day`, `Week`, `Month`, `Year`, `2Y`, `5Y`, `10Y`. `Sec` reads the in-memory tick buffer; everything else hits yfinance with a per-range TTL cache. |
| `GET`  | `/api/search?q=<text>` |   | Symbol search (ticker prefix or company name) via Finnhub's `/search`, filtered to plain US-style tickers. Returns up to 12 `{symbol, description, type}`. |
| `WS`   | `/ws` |   | Bidirectional stream. Client sends `{"type":"watch","symbols":["AAPL","MSFT"]}` to register interest (the backend ref-counts upstream Finnhub subscriptions). Server pushes `{"type":"tick","symbol","price_cents","prev_close_cents","timestamp_ms","source":"stream"\|"rest"}` on every trade. |

Quick example (substitute the actual user id from `GET /api/users`):

```bash
# Create a user (no header needed)
curl -s -X POST http://localhost:8000/api/users \
  -H 'Content-Type: application/json' \
  -d '{"name":"noam","starting_cash_cents":10000000}'

# Buy 5 shares of AAPL as user 1
curl -s -X POST http://localhost:8000/api/trades \
  -H 'Content-Type: application/json' \
  -H 'X-User-Id: 1' \
  -d '{"symbol":"AAPL","side":"BUY","quantity":5}'

# Snapshot for user 1
curl -s -H 'X-User-Id: 1' http://localhost:8000/api/portfolio | jq

# Public — no header needed
curl -s 'http://localhost:8000/api/history/NVDA?range=Year' | jq '.points | length'
```

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
