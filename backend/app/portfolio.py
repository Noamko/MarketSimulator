import sqlite3
from typing import Optional

from .models import Portfolio, Position
from .market_hours import is_market_open
from .price_hub import PriceHub


def snapshot(conn: sqlite3.Connection, hub: PriceHub) -> Portfolio:
    cash_row = conn.execute("SELECT cash_cents FROM account WHERE id = 1").fetchone()
    cash = int(cash_row["cash_cents"]) if cash_row else 0

    holdings = conn.execute(
        "SELECT symbol, "
        "       SUM(quantity_remaining)                          AS qty, "
        "       SUM(quantity_remaining * cost_basis_cents)       AS cost "
        "FROM lots GROUP BY symbol HAVING qty > 0 ORDER BY symbol"
    ).fetchall()

    positions: list[Position] = []
    market_value_total = 0
    for h in holdings:
        qty = int(h["qty"])
        cost = int(h["cost"])
        avg_cost = cost // qty if qty else 0
        tick = hub.latest_prices.get(h["symbol"])
        last_price: Optional[int] = tick.price_cents if tick else None
        mv: Optional[int] = last_price * qty if last_price is not None else None
        unrealized: Optional[int] = (last_price - avg_cost) * qty if last_price is not None else None
        if mv is not None:
            market_value_total += mv
        positions.append(Position(
            symbol=h["symbol"],
            quantity=qty,
            avg_cost_cents=avg_cost,
            last_price_cents=last_price,
            market_value_cents=mv,
            unrealized_pnl_cents=unrealized,
        ))

    realized_row = conn.execute(
        "SELECT COALESCE(SUM(realized_pnl_cents), 0) AS pnl "
        "FROM trades WHERE side = 'SELL'"
    ).fetchone()
    realized = int(realized_row["pnl"]) if realized_row else 0

    return Portfolio(
        cash_cents=cash,
        positions=positions,
        total_realized_pnl_cents=realized,
        total_equity_cents=cash + market_value_total,
        market_open=is_market_open(),
    )
