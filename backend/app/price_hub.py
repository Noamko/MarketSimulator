import asyncio
import json
import logging
from collections import Counter, deque
from dataclasses import dataclass
from typing import Deque, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from .config import FINNHUB_API_KEY, FINNHUB_WS_URL
from .finnhub_client import fetch_quote_cents

log = logging.getLogger("pricehub")


@dataclass(frozen=True)
class Tick:
    symbol: str
    price_cents: int
    timestamp_ms: int
    source: str  # "stream" or "rest"


class PriceHub:
    """One upstream Finnhub WS, fanned out to N browser-side async queues.

    - `subscribe(symbol)` / `unsubscribe(symbol)` adjust a ref-count; we send
      a Finnhub subscribe frame on 0->1 and unsubscribe on 1->0.
    - `register_listener()` / `unregister_listener(q)` add/remove a per-client
      `asyncio.Queue` that receives every Tick.
    - `latest_prices` is the cache of the most recent tick per symbol; the
      trading layer reads from this when executing orders.
    """

    TICK_BUFFER_SIZE = 1000

    def __init__(self) -> None:
        self.latest_prices: dict[str, Tick] = {}
        self.tick_history: dict[str, Deque[Tick]] = {}
        self._listeners: set[asyncio.Queue[Tick]] = set()
        self._ref_counts: Counter[str] = Counter()
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    def _record_tick(self, tick: Tick) -> None:
        self.latest_prices[tick.symbol] = tick
        buf = self.tick_history.get(tick.symbol)
        if buf is None:
            buf = deque(maxlen=self.TICK_BUFFER_SIZE)
            self.tick_history[tick.symbol] = buf
        buf.append(tick)

    # ---------- lifecycle ----------

    async def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="pricehub-upstream")

    async def stop(self) -> None:
        self._stop.set()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._task is not None:
            try:
                await self._task
            except Exception:
                pass
            self._task = None

    # ---------- listeners ----------

    def register_listener(self) -> asyncio.Queue[Tick]:
        q: asyncio.Queue[Tick] = asyncio.Queue(maxsize=1000)
        self._listeners.add(q)
        return q

    def unregister_listener(self, q: asyncio.Queue[Tick]) -> None:
        self._listeners.discard(q)

    # ---------- subscriptions ----------

    async def subscribe(self, symbol: str) -> None:
        symbol = symbol.upper()
        async with self._lock:
            self._ref_counts[symbol] += 1
            if self._ref_counts[symbol] == 1:
                await self._send_subscribe(symbol)
                # Seed cache via REST so the UI/trading has a price immediately.
                if symbol not in self.latest_prices:
                    asyncio.create_task(self._seed_price(symbol))

    async def unsubscribe(self, symbol: str) -> None:
        symbol = symbol.upper()
        async with self._lock:
            if self._ref_counts[symbol] <= 0:
                return
            self._ref_counts[symbol] -= 1
            if self._ref_counts[symbol] == 0:
                del self._ref_counts[symbol]
                await self._send_unsubscribe(symbol)

    async def _seed_price(self, symbol: str) -> None:
        try:
            price = await fetch_quote_cents(symbol)
        except Exception as e:
            log.warning("REST seed failed for %s: %s", symbol, e)
            return
        if price is None:
            return
        tick = Tick(symbol=symbol, price_cents=price, timestamp_ms=0, source="rest")
        if symbol not in self.latest_prices:
            self.latest_prices[symbol] = tick
        self._fanout(tick)

    # ---------- upstream wire protocol ----------

    async def _send_subscribe(self, symbol: str) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))
        except Exception as e:
            log.warning("upstream subscribe %s failed: %s", symbol, e)

    async def _send_unsubscribe(self, symbol: str) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"type": "unsubscribe", "symbol": symbol}))
        except Exception as e:
            log.warning("upstream unsubscribe %s failed: %s", symbol, e)

    async def _run(self) -> None:
        backoff = 1.0
        url = f"{FINNHUB_WS_URL}?token={FINNHUB_API_KEY}"
        while not self._stop.is_set():
            if not FINNHUB_API_KEY:
                log.error("FINNHUB_API_KEY missing; upstream WS disabled")
                await asyncio.sleep(30)
                continue
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    self._ws = ws
                    backoff = 1.0
                    # Re-subscribe everything currently ref-counted.
                    async with self._lock:
                        for sym in list(self._ref_counts):
                            await ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
                    log.info("upstream WS connected, %d symbols", len(self._ref_counts))
                    async for raw in ws:
                        self._handle_upstream(raw)
            except ConnectionClosed as e:
                log.warning("upstream WS closed: %s", e)
            except Exception as e:
                log.warning("upstream WS error: %s", e)
            finally:
                self._ws = None
            if self._stop.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    def _handle_upstream(self, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw)
        except Exception:
            return
        if msg.get("type") != "trade":
            return
        for t in msg.get("data", []) or []:
            try:
                symbol = t["s"]
                price_cents = int(round(float(t["p"]) * 100))
                ts = int(t.get("t", 0))
            except (KeyError, TypeError, ValueError):
                continue
            tick = Tick(symbol=symbol, price_cents=price_cents, timestamp_ms=ts, source="stream")
            self._record_tick(tick)
            self._fanout(tick)

    def _fanout(self, tick: Tick) -> None:
        # Non-blocking: if a client is slow, drop their oldest message.
        for q in list(self._listeners):
            if q.full():
                try:
                    q.get_nowait()
                except Exception:
                    pass
            try:
                q.put_nowait(tick)
            except Exception:
                pass


# Module-level singleton, wired up in main.py lifespan.
hub = PriceHub()
