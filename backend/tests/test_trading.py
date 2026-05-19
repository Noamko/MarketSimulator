import sqlite3
import time
from pathlib import Path

import pytest

from app.trading import buy, sell, TradingError

SCHEMA = Path(__file__).resolve().parents[1] / "app" / "schema.sql"


def make_db(cash_cents: int = 1_000_000, name: str = "tester") -> tuple[sqlite3.Connection, int]:
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text())
    cur = conn.execute("INSERT INTO users (name, cash_cents) VALUES (?, ?)", (name, cash_cents))
    return conn, int(cur.lastrowid)


def cash(conn, user_id) -> int:
    return int(conn.execute("SELECT cash_cents FROM users WHERE id = ?", (user_id,)).fetchone()["cash_cents"])


def holding(conn, user_id, symbol) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity_remaining), 0) AS q FROM lots WHERE user_id = ? AND symbol = ?",
        (user_id, symbol),
    ).fetchone()
    return int(row["q"])


def test_simple_buy_then_sell_profit():
    conn, uid = make_db(cash_cents=1_000_000)  # $10,000

    buy(conn, uid, "AAPL", quantity=10, price_cents=10_000)
    assert cash(conn, uid) == 1_000_000 - 100_000
    assert holding(conn, uid, "AAPL") == 10

    trade_id, pnl = sell(conn, uid, "AAPL", quantity=10, price_cents=12_000)
    assert pnl == (12_000 - 10_000) * 10
    assert cash(conn, uid) == 1_000_000 - 100_000 + 120_000
    assert holding(conn, uid, "AAPL") == 0


def test_partial_sell_keeps_remaining_lot():
    conn, uid = make_db(cash_cents=1_000_000)
    buy(conn, uid, "MSFT", 20, 5_000)

    _, pnl = sell(conn, uid, "MSFT", 5, 6_000)
    assert pnl == (6_000 - 5_000) * 5
    assert holding(conn, uid, "MSFT") == 15


def test_fifo_across_multiple_lots():
    conn, uid = make_db(cash_cents=10_000_000)
    buy(conn, uid, "TSLA", 10, 20_000)  # lot 1
    time.sleep(0.01)
    buy(conn, uid, "TSLA", 10, 25_000)  # lot 2

    _, pnl = sell(conn, uid, "TSLA", 15, 30_000)
    expected = (30_000 - 20_000) * 10 + (30_000 - 25_000) * 5
    assert pnl == expected
    assert holding(conn, uid, "TSLA") == 5

    rows = conn.execute(
        "SELECT quantity_remaining, cost_basis_cents FROM lots WHERE symbol = 'TSLA'"
    ).fetchall()
    assert len(rows) == 1
    assert int(rows[0]["quantity_remaining"]) == 5
    assert int(rows[0]["cost_basis_cents"]) == 25_000


def test_full_liquidation_across_lots():
    conn, uid = make_db(cash_cents=10_000_000)
    buy(conn, uid, "NVDA", 5, 50_000)
    time.sleep(0.01)
    buy(conn, uid, "NVDA", 5, 40_000)

    _, pnl = sell(conn, uid, "NVDA", 10, 45_000)
    assert pnl == (45_000 - 50_000) * 5 + (45_000 - 40_000) * 5
    assert holding(conn, uid, "NVDA") == 0


def test_insufficient_funds_rejects():
    conn, uid = make_db(cash_cents=1_000)
    with pytest.raises(TradingError):
        buy(conn, uid, "AAPL", 10, 10_000)
    assert conn.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"] == 0
    assert cash(conn, uid) == 1_000


def test_insufficient_shares_rejects():
    conn, uid = make_db()
    buy(conn, uid, "SPY", 5, 50_000)
    with pytest.raises(TradingError):
        sell(conn, uid, "SPY", 10, 50_000)
    assert holding(conn, uid, "SPY") == 5


def test_realized_pnl_persisted_on_trade_row():
    conn, uid = make_db()
    buy(conn, uid, "AAPL", 1, 10_000)
    sell(conn, uid, "AAPL", 1, 12_500)
    row = conn.execute(
        "SELECT side, realized_pnl_cents FROM trades WHERE side = 'SELL'"
    ).fetchone()
    assert int(row["realized_pnl_cents"]) == 2_500


def test_two_users_are_isolated():
    """Trades / holdings / cash for one user must not affect another."""
    conn, alice = make_db(cash_cents=1_000_000, name="alice")
    bob_cur = conn.execute("INSERT INTO users (name, cash_cents) VALUES ('bob', ?)", (500_000,))
    bob = int(bob_cur.lastrowid)

    buy(conn, alice, "AAPL", 5, 10_000)
    buy(conn, bob,   "AAPL", 3, 10_000)

    assert cash(conn, alice) == 1_000_000 - 50_000
    assert cash(conn, bob)   == 500_000   - 30_000
    assert holding(conn, alice, "AAPL") == 5
    assert holding(conn, bob,   "AAPL") == 3

    sell(conn, alice, "AAPL", 5, 12_000)
    # Bob's position must be untouched.
    assert holding(conn, alice, "AAPL") == 0
    assert holding(conn, bob,   "AAPL") == 3
