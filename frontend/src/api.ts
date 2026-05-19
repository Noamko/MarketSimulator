import type { HistoryResponse, Portfolio, Quote, RangeLabel, TradeRow } from "./types";

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = body.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

export function getPortfolio(): Promise<Portfolio> {
  return jsonFetch<Portfolio>("/api/portfolio");
}

export function getTrades(limit = 100): Promise<TradeRow[]> {
  return jsonFetch<TradeRow[]>(`/api/trades?limit=${limit}`);
}

export function getQuote(symbol: string): Promise<Quote> {
  return jsonFetch<Quote>(`/api/quote/${encodeURIComponent(symbol)}`);
}

export function getHistory(symbol: string, range: RangeLabel): Promise<HistoryResponse> {
  return jsonFetch<HistoryResponse>(
    `/api/history/${encodeURIComponent(symbol)}?range=${encodeURIComponent(range)}`,
  );
}

export function postTrade(symbol: string, side: "BUY" | "SELL", quantity: number) {
  return jsonFetch<{ trade_id: number; price_cents: number; realized_pnl_cents: number | null }>(
    "/api/trades",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, side, quantity }),
    },
  );
}
