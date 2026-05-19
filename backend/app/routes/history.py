import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query

from ..history import get_history, supported_ranges
from ..price_hub import hub

log = logging.getLogger("history")
router = APIRouter()


@router.get("/history/{symbol}")
async def get_symbol_history(symbol: str, range: str = Query(...)):
    if range not in supported_ranges():
        raise HTTPException(
            status_code=400,
            detail=f"unsupported range {range!r}; allowed: {supported_ranges()}",
        )
    try:
        points = await asyncio.to_thread(get_history, symbol, range, hub)
    except Exception as e:
        log.exception("history fetch failed for %s/%s", symbol, range)
        raise HTTPException(status_code=502, detail=f"upstream history fetch failed: {e}")

    return {
        "symbol": symbol.upper(),
        "range": range,
        "points": [
            {"timestamp_ms": p.timestamp_ms, "price_cents": p.price_cents}
            for p in points
        ],
    }
