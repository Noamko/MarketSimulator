import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..price_hub import hub

log = logging.getLogger("ws")
router = APIRouter()


@router.websocket("/ws")
async def stream(ws: WebSocket) -> None:
    await ws.accept()
    queue = hub.register_listener()
    watched: set[str] = set()

    async def pump_ticks() -> None:
        try:
            while True:
                tick = await queue.get()
                await ws.send_json({
                    "type": "tick",
                    "symbol": tick.symbol,
                    "price_cents": tick.price_cents,
                    "timestamp_ms": tick.timestamp_ms,
                    "source": tick.source,
                })
        except (WebSocketDisconnect, RuntimeError):
            return

    async def read_commands() -> None:
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "watch":
                    new_set = {str(s).upper() for s in msg.get("symbols", []) if s}
                    to_add = new_set - watched
                    to_remove = watched - new_set
                    for s in to_add:
                        await hub.subscribe(s)
                    for s in to_remove:
                        await hub.unsubscribe(s)
                    watched.clear()
                    watched.update(new_set)
                    # Send a snapshot of any prices already cached so the UI
                    # doesn't have to wait for the next trade tick.
                    for s in new_set:
                        tick = hub.latest_prices.get(s)
                        if tick is not None:
                            await ws.send_json({
                                "type": "tick",
                                "symbol": tick.symbol,
                                "price_cents": tick.price_cents,
                                "timestamp_ms": tick.timestamp_ms,
                                "source": tick.source,
                            })
        except (WebSocketDisconnect, RuntimeError):
            return

    pump = asyncio.create_task(pump_ticks())
    reader = asyncio.create_task(read_commands())
    try:
        done, pending = await asyncio.wait({pump, reader}, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
    finally:
        for s in list(watched):
            await hub.unsubscribe(s)
        hub.unregister_listener(queue)
