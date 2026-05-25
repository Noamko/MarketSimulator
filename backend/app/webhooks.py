"""Outbound webhooks: POST a JSON payload to a user-supplied URL when an event
fires.

Four event types, each with its own source:

- PRICE_TARGET       — a symbol crosses a target price (observed via PriceHub ticks)
- MARKET_STATUS      — the US market opens or closes (market_hours poller transition)
- TRADE_EXECUTED     — a buy/sell commits (trade route)
- PORTFOLIO_THRESHOLD— account equity or realized P&L crosses a value (portfolio_watcher)

Delivery is best-effort fire-and-forget: a single httpx POST scheduled on the
event loop so a slow/dead endpoint never blocks the source. Errors are swallowed
and logged at WARNING. Crossing detection (fire once on the transition, not on
every tick past the target) uses the persisted `last_value_cents` baseline.
"""

import asyncio
import logging
import time
from typing import Optional

import httpx

from .db import get_conn
from .portfolio import snapshot
from .price_hub import Tick, hub

log = logging.getLogger("webhooks")

_DELIVERY_TIMEOUT_S = 5.0
PRICE_WATCH_INTERVAL_S = 30.0
PORTFOLIO_WATCH_INTERVAL_S = 15.0

# Symbols we keep subscribed on the PriceHub on behalf of webhook rules, so price
# and portfolio events fire even when no browser is open.
_system_subs: set[str] = set()
# PRICE_TARGET symbols only — gates per-tick evaluation so we don't hit the DB
# for every tick of a symbol that has no price rule.
_price_rule_symbols: set[str] = set()
_reconcile_lock = asyncio.Lock()


# --------------------------------------------------------------------------- #
# Dispatch (fire-and-forget)
# --------------------------------------------------------------------------- #

def _now_ms() -> int:
    return int(time.time() * 1000)


def _envelope(row, data: dict) -> dict:
    return {
        "event": row["event_type"],
        "webhook_id": row["id"],
        "user_id": row["user_id"],
        "ts": _now_ms(),
        "data": data,
    }


def _dispatch(url: str, payload: dict) -> None:
    """Schedule a single best-effort POST. Returns immediately; never blocks."""
    try:
        asyncio.create_task(_deliver(url, payload))
    except RuntimeError:
        # No running event loop (shouldn't happen — all callers run on the loop).
        log.warning("no event loop to dispatch webhook to %s", url)


async def _deliver(url: str, payload: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT_S) as client:
            await client.post(url, json=payload)
        log.info("webhook delivered: %s -> %s", payload.get("event"), url)
    except Exception as e:  # swallow: delivery is best-effort
        log.warning("webhook delivery failed %s: %s", url, e)


def _crossed(prev: Optional[int], current: int, target: int, direction: str) -> bool:
    """True when `current` crosses `target` in `direction` relative to `prev`.

    The first observation (prev is None) never fires — it just seeds the baseline,
    so creating a rule below the current price doesn't fire retroactively.
    """
    if prev is None:
        return False
    if direction == "above":
        return prev < target <= current
    return prev > target >= current  # "below"


# --------------------------------------------------------------------------- #
# Per-event evaluators
# --------------------------------------------------------------------------- #

def evaluate_price_tick(symbol: str, price_cents: int) -> None:
    """Check active PRICE_TARGET rules for `symbol` against a new price."""
    symbol = symbol.upper()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM webhooks "
            "WHERE enabled = 1 AND event_type = 'PRICE_TARGET' AND symbol = ?",
            (symbol,),
        ).fetchall()
        for r in rows:
            if _crossed(r["last_value_cents"], price_cents, r["target_cents"], r["direction"]):
                _dispatch(r["url"], _envelope(r, {
                    "symbol": symbol,
                    "price_cents": price_cents,
                    "target_cents": r["target_cents"],
                    "direction": r["direction"],
                }))
                _mark_fired(conn, r, price_cents)
            else:
                conn.execute(
                    "UPDATE webhooks SET last_value_cents = ? WHERE id = ?",
                    (price_cents, r["id"]),
                )


async def fire_market_transition(is_open: bool, source: str) -> None:
    """Fire all enabled MARKET_STATUS rules on an open/close transition."""
    transition = "open" if is_open else "close"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM webhooks WHERE enabled = 1 AND event_type = 'MARKET_STATUS'"
        ).fetchall()
    for r in rows:
        _dispatch(r["url"], _envelope(r, {
            "is_open": is_open,
            "transition": transition,
            "source": source,
        }))


def fire_trade_executed(
    user_id: int,
    trade_id: int,
    symbol: str,
    side: str,
    quantity: int,
    price_cents: int,
    realized_pnl_cents: Optional[int],
) -> None:
    """Fire the calling user's enabled TRADE_EXECUTED rules. Non-blocking."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM webhooks "
            "WHERE enabled = 1 AND event_type = 'TRADE_EXECUTED' AND user_id = ?",
            (user_id,),
        ).fetchall()
    for r in rows:
        _dispatch(r["url"], _envelope(r, {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price_cents": price_cents,
            "realized_pnl_cents": realized_pnl_cents,
        }))


def evaluate_portfolio(user_id: int, equity_cents: int, realized_pnl_cents: int) -> None:
    """Check a user's PORTFOLIO_THRESHOLD rules against a fresh snapshot."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM webhooks "
            "WHERE enabled = 1 AND event_type = 'PORTFOLIO_THRESHOLD' AND user_id = ?",
            (user_id,),
        ).fetchall()
        for r in rows:
            value = equity_cents if r["metric"] == "equity" else realized_pnl_cents
            if _crossed(r["last_value_cents"], value, r["target_cents"], r["direction"]):
                _dispatch(r["url"], _envelope(r, {
                    "metric": r["metric"],
                    "value_cents": value,
                    "target_cents": r["target_cents"],
                    "direction": r["direction"],
                }))
                _mark_fired(conn, r, value)
            else:
                conn.execute(
                    "UPDATE webhooks SET last_value_cents = ? WHERE id = ?",
                    (value, r["id"]),
                )


def _mark_fired(conn, row, value_cents: int) -> None:
    """Record a fire; disable one-shot rules so they don't re-arm."""
    if row["one_shot"]:
        conn.execute(
            "UPDATE webhooks SET last_value_cents = ?, last_fired_at = CURRENT_TIMESTAMP, "
            "enabled = 0 WHERE id = ?",
            (value_cents, row["id"]),
        )
    else:
        conn.execute(
            "UPDATE webhooks SET last_value_cents = ?, last_fired_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (value_cents, row["id"]),
        )


# --------------------------------------------------------------------------- #
# PriceHub integration
# --------------------------------------------------------------------------- #

def on_tick(tick: Tick) -> None:
    """Tick observer registered on the PriceHub (sync; runs in the WS loop).

    Schedules evaluation only for symbols that actually have a price rule, so the
    hot tick path stays cheap for everything else.
    """
    if tick.symbol not in _price_rule_symbols:
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return  # not on the loop (shouldn't happen — observer runs in the WS task)
    asyncio.create_task(_run_price_eval(tick.symbol, tick.price_cents))


async def _run_price_eval(symbol: str, price_cents: int) -> None:
    # evaluate_price_tick does only quick local SQLite work.
    evaluate_price_tick(symbol, price_cents)


def _active_price_symbols() -> set[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM webhooks "
            "WHERE enabled = 1 AND event_type = 'PRICE_TARGET' AND symbol IS NOT NULL"
        ).fetchall()
    return {r["symbol"] for r in rows}


def _portfolio_position_symbols() -> set[str]:
    """Held-position symbols for users who have a portfolio rule — keeping these
    subscribed means equity is computed from live prices, not stale/missing ones."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM lots WHERE quantity_remaining > 0 AND user_id IN "
            "(SELECT DISTINCT user_id FROM webhooks "
            " WHERE enabled = 1 AND event_type = 'PORTFOLIO_THRESHOLD')"
        ).fetchall()
    return {r["symbol"] for r in rows}


async def reconcile_subscriptions() -> None:
    """Bring PriceHub subscriptions in line with what the active rules need.

    Reuses the hub's ref-count contract: we hold one ref per needed symbol on the
    webhook system's behalf; a browser watching the same symbol just adds another.
    """
    global _price_rule_symbols
    async with _reconcile_lock:
        price_syms = _active_price_symbols()
        needed = price_syms | _portfolio_position_symbols()
        _price_rule_symbols = price_syms

        for sym in needed - _system_subs:
            await hub.subscribe(sym)
            _system_subs.add(sym)
        for sym in _system_subs - needed:
            await hub.unsubscribe(sym)
            _system_subs.discard(sym)


# --------------------------------------------------------------------------- #
# Background watchers (started in main.py lifespan)
# --------------------------------------------------------------------------- #

async def price_rule_watcher(interval: float = PRICE_WATCH_INTERVAL_S) -> None:
    """Periodically reconcile subscriptions (catches one-shot disables and any
    rules created while the reconcile-on-write path wasn't taken)."""
    while True:
        try:
            await reconcile_subscriptions()
        except Exception as e:
            log.warning("subscription reconcile failed: %s", e)
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise


async def portfolio_watcher(interval: float = PORTFOLIO_WATCH_INTERVAL_S) -> None:
    """Evaluate PORTFOLIO_THRESHOLD rules against fresh snapshots."""
    while True:
        try:
            with get_conn() as conn:
                uids = [
                    r["user_id"]
                    for r in conn.execute(
                        "SELECT DISTINCT user_id FROM webhooks "
                        "WHERE enabled = 1 AND event_type = 'PORTFOLIO_THRESHOLD'"
                    ).fetchall()
                ]
                snaps = [(uid, snapshot(conn, hub, uid)) for uid in uids]
            for uid, snap in snaps:
                evaluate_portfolio(uid, snap.total_equity_cents, snap.total_realized_pnl_cents)
        except Exception as e:
            log.warning("portfolio watcher failed: %s", e)
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
