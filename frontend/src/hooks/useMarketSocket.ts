import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Tick } from "../types";

type PriceMap = Record<string, Tick>;

export interface UseMarketSocket {
  prices: PriceMap;
  connected: boolean;
  onTick: (cb: (tick: Tick) => void) => () => void;
}

export function useMarketSocket(symbols: string[]): UseMarketSocket {
  const [prices, setPrices] = useState<PriceMap>({});
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const symbolsRef = useRef<string[]>(symbols);
  const tickListeners = useRef<Set<(t: Tick) => void>>(new Set());
  const backoffRef = useRef(1000);
  symbolsRef.current = symbols;

  const sendWatch = useCallback((ws: WebSocket, list: string[]) => {
    try {
      ws.send(JSON.stringify({ type: "watch", symbols: list }));
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const open = () => {
      if (cancelled) return;
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        backoffRef.current = 1000;
        sendWatch(ws, symbolsRef.current);
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "tick") {
            const tick: Tick = {
              symbol: msg.symbol,
              price_cents: msg.price_cents,
              timestamp_ms: msg.timestamp_ms,
              source: msg.source,
            };
            setPrices((prev) => {
              const existing = prev[tick.symbol];
              // Don't overwrite a stream tick with a (stale) rest seed.
              if (existing && existing.source === "stream" && tick.source === "rest") return prev;
              return { ...prev, [tick.symbol]: tick };
            });
            tickListeners.current.forEach((cb) => cb(tick));
          }
        } catch { /* ignore */ }
      };
      ws.onclose = () => {
        setConnected(false);
        if (cancelled) return;
        const delay = Math.min(backoffRef.current, 30_000);
        backoffRef.current = Math.min(backoffRef.current * 2, 30_000);
        reconnectTimer = setTimeout(open, delay);
      };
      ws.onerror = () => {
        try { ws.close(); } catch { /* ignore */ }
      };
    };

    open();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      try { wsRef.current?.close(); } catch { /* ignore */ }
    };
  }, [sendWatch]);

  // When the symbol list changes, tell the backend.
  useEffect(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      sendWatch(ws, symbols);
    }
  }, [symbols, sendWatch]);

  const onTick = useCallback((cb: (t: Tick) => void) => {
    tickListeners.current.add(cb);
    return () => { tickListeners.current.delete(cb); };
  }, []);

  return useMemo(() => ({ prices, connected, onTick }), [prices, connected, onTick]);
}
