"""Historical price series for the chart timeframe buttons.

`Sec` reads from the in-memory tick buffer that PriceHub fills from the Finnhub
WebSocket stream. Every other range fetches OHLC bars from yfinance (Yahoo) and
returns the closing price per bar.
"""

import time
from dataclasses import dataclass
from typing import Optional

import yfinance as yf

from .price_hub import PriceHub


@dataclass(frozen=True)
class Point:
    timestamp_ms: int
    price_cents: int


# range label -> (yfinance period, yfinance interval)
# 'Sec' is handled specially: served from PriceHub's recent-tick buffer.
RANGE_PARAMS: dict[str, tuple[str, str]] = {
    "Min":   ("1d",  "1m"),
    "Hour":  ("5d",  "5m"),
    "Day":   ("5d",  "15m"),
    "Week":  ("1mo", "1h"),
    "Month": ("3mo", "1d"),
    "Year":  ("1y",  "1d"),
    "2Y":    ("2y",  "1wk"),
    "5Y":    ("5y",  "1wk"),
    "10Y":   ("10y", "1mo"),
}

# Per-bucket TTLs (seconds). Intraday data updates often; daily/weekly rarely.
TTL_BY_RANGE: dict[str, float] = {
    "Min":   15,
    "Hour":  30,
    "Day":   60,
    "Week":  120,
    "Month": 600,
    "Year":  3600,
    "2Y":    3600,
    "5Y":    21600,
    "10Y":   21600,
}

_cache: dict[tuple[str, str], tuple[float, list[Point]]] = {}


def supported_ranges() -> list[str]:
    return ["Sec", *RANGE_PARAMS.keys()]


def get_history(symbol: str, range_label: str, hub: PriceHub) -> list[Point]:
    symbol = symbol.upper()

    if range_label == "Sec":
        buf = hub.tick_history.get(symbol)
        if not buf:
            tick = hub.latest_prices.get(symbol)
            if tick is None:
                return []
            return [Point(timestamp_ms=tick.timestamp_ms or int(time.time() * 1000),
                          price_cents=tick.price_cents)]
        return [Point(timestamp_ms=t.timestamp_ms or 0, price_cents=t.price_cents) for t in buf]

    params = RANGE_PARAMS.get(range_label)
    if params is None:
        raise ValueError(f"unsupported range: {range_label!r}")
    period, interval = params

    cache_key = (symbol, range_label)
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached is not None and (now - cached[0]) < TTL_BY_RANGE[range_label]:
        return cached[1]

    points = _fetch_yfinance(symbol, period, interval)
    _cache[cache_key] = (now, points)
    return points


def _fetch_yfinance(symbol: str, period: str, interval: str) -> list[Point]:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=False)
    if df is None or df.empty or "Close" not in df.columns:
        return []
    out: list[Point] = []
    for ts, row in df["Close"].items():
        try:
            price = float(row)
        except (TypeError, ValueError):
            continue
        if price != price:  # NaN check
            continue
        epoch_ms = int(ts.timestamp() * 1000)
        out.append(Point(timestamp_ms=epoch_ms, price_cents=int(round(price * 100))))
    return out
