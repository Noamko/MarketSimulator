from fastapi import APIRouter, HTTPException

from ..models import Quote
from ..price_hub import hub
from ..finnhub_client import fetch_quote_cents

router = APIRouter()


@router.get("/quote/{symbol}", response_model=Quote)
async def get_quote(symbol: str) -> Quote:
    symbol = symbol.upper()
    tick = hub.latest_prices.get(symbol)
    if tick is not None:
        return Quote(
            symbol=symbol,
            price_cents=tick.price_cents,
            source=tick.source,  # type: ignore[arg-type]
            timestamp_ms=tick.timestamp_ms,
        )
    price = await fetch_quote_cents(symbol)
    if price is None or price <= 0:
        raise HTTPException(status_code=404, detail=f"no price available for {symbol}")
    return Quote(symbol=symbol, price_cents=price, source="rest", timestamp_ms=None)
