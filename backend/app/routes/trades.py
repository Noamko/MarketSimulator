from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_conn
from ..models import TradeRequest, TradeRow
from ..price_hub import hub
from ..finnhub_client import fetch_quote_cents
from ..trading import buy, sell, TradingError
from ..users import get_current_user_id

router = APIRouter()


async def _price_for(symbol: str) -> int:
    tick = hub.latest_prices.get(symbol.upper())
    if tick is not None:
        return tick.price_cents
    price = await fetch_quote_cents(symbol)
    if price is None or price <= 0:
        raise HTTPException(status_code=404, detail=f"no price available for {symbol}")
    return price


@router.post("/trades")
async def post_trade(req: TradeRequest, user_id: int = Depends(get_current_user_id)):
    price = await _price_for(req.symbol)
    try:
        with get_conn() as conn:
            if req.side == "BUY":
                trade_id = buy(conn, user_id, req.symbol, req.quantity, price)
                return {"trade_id": trade_id, "price_cents": price, "realized_pnl_cents": None}
            else:
                trade_id, pnl = sell(conn, user_id, req.symbol, req.quantity, price)
                return {"trade_id": trade_id, "price_cents": price, "realized_pnl_cents": pnl}
    except TradingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/trades", response_model=list[TradeRow])
def list_trades(
    user_id: int = Depends(get_current_user_id),
    limit: int = Query(default=100, ge=1, le=1000),
):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, symbol, side, quantity, price_cents, executed_at, realized_pnl_cents "
            "FROM trades WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [TradeRow(**dict(r)) for r in rows]
