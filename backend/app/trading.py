import sqlite3

from .db import transaction


class TradingError(Exception):
    """Validation error: insufficient cash, insufficient shares, no price, etc."""


def _get_cash(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute("SELECT cash_cents FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise TradingError(f"user {user_id} not found")
    return int(row["cash_cents"])


def buy(conn: sqlite3.Connection, user_id: int, symbol: str, quantity: int, price_cents: int) -> int:
    """Execute a BUY for a user. Returns the new trades.id."""
    if quantity <= 0:
        raise TradingError("quantity must be positive")
    if price_cents <= 0:
        raise TradingError("price unavailable for symbol")

    symbol = symbol.upper()
    cost = price_cents * quantity

    with transaction(conn):
        cash = _get_cash(conn, user_id)
        if cash < cost:
            raise TradingError(
                f"insufficient funds: need ${cost/100:,.2f}, have ${cash/100:,.2f}"
            )
        cur = conn.execute(
            "INSERT INTO trades (user_id, symbol, side, quantity, price_cents) "
            "VALUES (?, ?, 'BUY', ?, ?)",
            (user_id, symbol, quantity, price_cents),
        )
        trade_id = cur.lastrowid
        conn.execute(
            "INSERT INTO lots (user_id, symbol, quantity_remaining, cost_basis_cents, trade_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, symbol, quantity, price_cents, trade_id),
        )
        conn.execute(
            "UPDATE users SET cash_cents = cash_cents - ? WHERE id = ?",
            (cost, user_id),
        )
    return int(trade_id)


def sell(conn: sqlite3.Connection, user_id: int, symbol: str, quantity: int, price_cents: int) -> tuple[int, int]:
    """Execute a SELL for a user using FIFO across their open lots.

    Returns (trade_id, realized_pnl_cents).
    """
    if quantity <= 0:
        raise TradingError("quantity must be positive")
    if price_cents <= 0:
        raise TradingError("price unavailable for symbol")

    symbol = symbol.upper()
    proceeds = price_cents * quantity

    with transaction(conn):
        lots = conn.execute(
            "SELECT id, quantity_remaining, cost_basis_cents FROM lots "
            "WHERE user_id = ? AND symbol = ? ORDER BY opened_at ASC, id ASC",
            (user_id, symbol),
        ).fetchall()

        held = sum(int(l["quantity_remaining"]) for l in lots)
        if held < quantity:
            raise TradingError(
                f"insufficient shares: trying to sell {quantity} {symbol}, holding {held}"
            )

        remaining = quantity
        realized_pnl = 0
        for lot in lots:
            if remaining == 0:
                break
            lot_qty = int(lot["quantity_remaining"])
            consumed = min(remaining, lot_qty)
            realized_pnl += (price_cents - int(lot["cost_basis_cents"])) * consumed
            new_qty = lot_qty - consumed
            if new_qty == 0:
                conn.execute("DELETE FROM lots WHERE id = ?", (lot["id"],))
            else:
                conn.execute(
                    "UPDATE lots SET quantity_remaining = ? WHERE id = ?",
                    (new_qty, lot["id"]),
                )
            remaining -= consumed

        cur = conn.execute(
            "INSERT INTO trades (user_id, symbol, side, quantity, price_cents, realized_pnl_cents) "
            "VALUES (?, ?, 'SELL', ?, ?, ?)",
            (user_id, symbol, quantity, price_cents, realized_pnl),
        )
        trade_id = cur.lastrowid
        conn.execute(
            "UPDATE users SET cash_cents = cash_cents + ? WHERE id = ?",
            (proceeds, user_id),
        )
    return int(trade_id), realized_pnl
