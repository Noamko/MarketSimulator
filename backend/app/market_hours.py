"""Market-open state, sourced from the web (not the local machine clock).

A background task polls — in order of preference:

1. Finnhub `/stock/market-status`. Authoritative isOpen flag plus holiday and
   pre/post-market session info. May fail in environments with a broken local
   clock (TLS cert "not yet valid" / "expired" errors are clock-dependent).
2. Plain-HTTP `Date` response header from a public web server. Plain HTTP means
   we don't depend on the local clock for TLS, so this works even when the
   machine clock is hours off. We then compute the NYSE window against
   `America/New_York` via `zoneinfo`. This path doesn't know about US market
   holidays — half-days, Memorial Day, Thanksgiving, etc.
3. The local clock, as a last resort.

`is_market_open()` reads the cached result synchronously so existing sync code
paths (portfolio snapshot, /api/health) don't need to be made async.
"""

import asyncio
import logging
from datetime import datetime, time, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from zoneinfo import ZoneInfo

import httpx

from .finnhub_client import fetch_market_status

NY = ZoneInfo("America/New_York")
log = logging.getLogger("market_hours")

POLL_INTERVAL_S = 60.0

# Plain-HTTP probes for current real UTC via the Date response header.
# Plain HTTP (no TLS) so we don't depend on the local clock being right.
TIME_PROBES = (
    "http://www.google.com",
    "http://www.cloudflare.com",
    "http://example.com",
)

_state: dict = {
    "is_open": False,
    "source": "uninitialised",
    "session": None,        # Finnhub: 'pre-market' | 'regular' | 'post-market' | None
    "holiday": None,
    "remote_utc": None,     # ISO string of the UTC we used for the decision
}


def is_market_open() -> bool:
    return bool(_state["is_open"])


def market_state() -> dict:
    """Diagnostic snapshot exposed via /api/health."""
    return dict(_state)


def _check_open(now_utc: datetime) -> bool:
    eastern = now_utc.astimezone(NY)
    if eastern.weekday() >= 5:
        return False
    return time(9, 30) <= eastern.time() <= time(16, 0)


async def fetch_world_utc() -> Optional[datetime]:
    """Return real current UTC by reading a remote server's HTTP Date header.

    Tries plain-HTTP candidates in order and returns the first parseable Date.
    """
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
        for url in TIME_PROBES:
            try:
                resp = await client.head(url)
                raw = resp.headers.get("date") or resp.headers.get("Date")
                if not raw:
                    continue
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception as e:
                log.debug("time probe %s failed: %s", url, e)
                continue
    return None


async def _poll_once() -> None:
    # 1. Finnhub — authoritative, with holiday awareness.
    try:
        data = await fetch_market_status()
    except Exception as e:
        log.info("market-status (finnhub) unavailable: %s — falling back to web-time", e)
        data = None

    if data and isinstance(data.get("isOpen"), bool):
        _state["is_open"] = bool(data["isOpen"])
        _state["source"] = "finnhub"
        _state["session"] = data.get("session")
        _state["holiday"] = data.get("holiday")
        _state["remote_utc"] = None
        return

    # 2. Web-sourced real UTC + zoneinfo NYSE window (no holiday awareness).
    remote_utc = await fetch_world_utc()
    if remote_utc is not None:
        _state["is_open"] = _check_open(remote_utc)
        _state["source"] = "remote-date-header"
        _state["session"] = None
        _state["holiday"] = None
        _state["remote_utc"] = remote_utc.isoformat()
        return

    # 3. Local clock — best effort if the network is down too.
    local_utc = datetime.now(timezone.utc)
    _state["is_open"] = _check_open(local_utc)
    _state["source"] = "local-clock-fallback"
    _state["session"] = None
    _state["holiday"] = None
    _state["remote_utc"] = None
    log.warning("market_hours: both upstreams failed; using local clock (%s)", local_utc.isoformat())


async def market_status_poller(interval: float = POLL_INTERVAL_S) -> None:
    """Long-lived background task. Started by main.py's lifespan."""
    while True:
        await _poll_once()
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
