import httpx

from .config import FINNHUB_API_KEY, FINNHUB_REST_URL


class FinnhubError(RuntimeError):
    pass


async def fetch_quote_cents(symbol: str) -> int | None:
    """Return current price (or last close, when market is closed) as integer cents.

    Finnhub's /quote endpoint returns `c` = current price as a float. Returns
    None if the symbol is unknown (Finnhub returns c=0 for invalid symbols).
    """
    if not FINNHUB_API_KEY:
        raise FinnhubError("FINNHUB_API_KEY is not set; copy .env.example to .env and fill it in")

    params = {"symbol": symbol.upper(), "token": FINNHUB_API_KEY}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{FINNHUB_REST_URL}/quote", params=params)
        resp.raise_for_status()
        data = resp.json()

    price = data.get("c")
    if not price:
        return None
    return int(round(float(price) * 100))
