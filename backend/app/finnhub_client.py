import httpx

from .config import FINNHUB_API_KEY, FINNHUB_REST_URL


class FinnhubError(RuntimeError):
    pass


async def search_symbols(query: str, limit: int = 12) -> list[dict]:
    """Return matching symbols from Finnhub's free /search endpoint.

    Each result is `{symbol, description, type}`. We filter to entries where
    `symbol == displaySymbol` (skips exotic international suffix variants).
    """
    query = query.strip()
    if not query:
        return []
    if not FINNHUB_API_KEY:
        raise FinnhubError("FINNHUB_API_KEY is not set; copy .env.example to .env and fill it in")

    params = {"q": query, "token": FINNHUB_API_KEY}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{FINNHUB_REST_URL}/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    out: list[dict] = []
    for r in data.get("result", []) or []:
        symbol = r.get("symbol") or ""
        # Restrict to plain US-style tickers (no dots, colons, or suffixes).
        if not symbol or not symbol.isascii() or not symbol.replace("-", "").isalpha():
            continue
        out.append({
            "symbol": symbol,
            "description": r.get("description") or "",
            "type": r.get("type") or "",
        })
        if len(out) >= limit:
            break
    return out


def _to_cents(x) -> int | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not v:
        return None
    return int(round(v * 100))


async def fetch_quote_full(symbol: str) -> tuple[int | None, int | None]:
    """Return (current_price_cents, previous_close_cents) from Finnhub /quote.

    Finnhub returns `c` (current) and `pc` (previous close) as floats. Either
    can be 0 for unknown/invalid symbols → returned as None.
    """
    if not FINNHUB_API_KEY:
        raise FinnhubError("FINNHUB_API_KEY is not set; copy .env.example to .env and fill it in")

    params = {"symbol": symbol.upper(), "token": FINNHUB_API_KEY}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{FINNHUB_REST_URL}/quote", params=params)
        resp.raise_for_status()
        data = resp.json()
    return _to_cents(data.get("c")), _to_cents(data.get("pc"))


async def fetch_quote_cents(symbol: str) -> int | None:
    current, _ = await fetch_quote_full(symbol)
    return current


async def fetch_market_status() -> dict | None:
    """Query Finnhub's /stock/market-status for US exchanges.

    Returns the raw dict (`{isOpen, session, holiday, timezone, t}`) or None
    when no API key is configured. The endpoint is on Finnhub's free tier and
    correctly accounts for weekends, NYSE/NASDAQ holidays, and half-days.
    """
    if not FINNHUB_API_KEY:
        return None
    params = {"exchange": "US", "token": FINNHUB_API_KEY}
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(f"{FINNHUB_REST_URL}/stock/market-status", params=params)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        return None
    return data
