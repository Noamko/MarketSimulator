import sqlite3
import time
from pathlib import Path

import pytest

from app.trading import buy, sell, TradingError

SCHEMA = Path(__file__).resolve().parents[1] / "app" / "schema.sql"


def make_db(cash_cents: int = 1_000_000) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text())
    conn.execute("INSERT INTO account (id, cash_cents) VALUES (1, ?)", (cash_cents,))
    return conn


def cash(conn) -> int:
    return int(conn.execute("SELECT cash_cents FROM account WHERE id = 1").fetchone()["cash_cents"])


def holding(conn, symbol: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity_remaining), 0) AS q FROM lots WHERE symbol = ?",
        (symbol,),
    ).fetchone()
    return int(row["q"])


def test_simple_buy_then_sell_profit():
    conn = make_db(cash_cents=1_000_000)  # $10,000

    buy(conn, "AAPL", quantity=10, price_cents=10_000)  # 10 @ $100 = $1,000
    assert cash(conn) == 1_000_000 - 100_000
    assert holding(conn, "AAPL") == 10

    trade_id, pnl = sell(conn, "AAPL", quantity=10, price_cents=12_000)  # @ $120
    assert pnl == (12_000 - 10_000) * 10  # $200 profit -> 20_000 cents
    assert cash(conn) == 1_000_000 - 100_000 + 120_000
    assert holding(conn, "AAPL") == 0


def test_partial_sell_keeps_remaining_lot():
    conn = make_db(cash_cents=1_000_000)
    buy(conn, "MSFT", 20, 5_000)  # 20 @ $50

    _, pnl = sell(conn, "MSFT", 5, 6_000)  # 5 @ $60
    assert pnl == (6_000 - 5_000) * 5
    assert holding(conn, "MSFT") == 15


def test_fifo_across_multiple_lots():
    conn = make_db(cash_cents=10_000_000)
    # Two lots at different prices, with distinct timestamps so order is deterministic.
    buy(conn, "TSLA", 10, 20_000)  # lot 1: 10 @ $200
    time.sleep(0.01)
    buy(conn, "TSLA", 10, 25_000)  # lot 2: 10 @ $250

    # Sell 15 @ $300: should consume all 10 of lot 1, then 5 of lot 2.
    _, pnl = sell(conn, "TSLA", 15, 30_000)
    expected = (30_000 - 20_000) * 10 + (30_000 - 25_000) * 5
    assert pnl == expected
    assert holding(conn, "TSLA") == 5

    # The surviving lot should be lot 2 with 5 shares remaining at $250 cost basis.
    rows = conn.execute(
        "SELECT quantity_remaining, cost_basis_cents FROM lots WHERE symbol = 'TSLA'"
    ).fetchall()
    assert len(rows) == 1
    assert int(rows[0]["quantity_remaining"]) == 5
    assert int(rows[0]["cost_basis_cents"]) == 25_000


def test_full_liquidation_across_lots():
    conn = make_db(cash_cents=10_000_000)
    buy(conn, "NVDA", 5, 50_000)
    time.sleep(0.01)
    buy(conn, "NVDA", 5, 40_000)

    _, pnl = sell(conn, "NVDA", 10, 45_000)
    # 5 sold from lot 1 at -$50/share, 5 from lot 2 at +$50/share
    assert pnl == (45_000 - 50_000) * 5 + (45_000 - 40_000) * 5
    assert holding(conn, "NVDA") == 0
    assert conn.execute("SELECT COUNT(*) c FROM lots WHERE symbol='NVDA'").fetchone()["c"] == 0


def test_insufficient_funds_rejects():
    conn = make_db(cash_cents=1_000)  # $10
    with pytest.raises(TradingError):
        buy(conn, "AAPL", 10, 10_000)  # needs $1,000
    # Atomicity check: no trade row created.
    assert conn.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"] == 0
    assert cash(conn) == 1_000


def test_insufficient_shares_rejects():
    conn = make_db()
    buy(conn, "SPY", 5, 50_000)
    with pytest.raises(TradingError):
        sell(conn, "SPY", 10, 50_000)
    assert holding(conn, "SPY") == 5


def test_realized_pnl_persisted_on_trade_row():
    conn = make_db()
    buy(conn, "AAPL", 1, 10_000)
    sell(conn, "AAPL", 1, 12_500)
    row = conn.execute(
        "SELECT side, realized_pnl_cents FROM trades WHERE side = 'SELL'"
    ).fetchone()
    assert int(row["realized_pnl_cents"]) == 2_500
