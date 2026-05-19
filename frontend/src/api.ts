import type {
  HistoryResponse, Portfolio, Quote, RangeLabel,
  SearchResponse, TradeRow, User,
} from "./types";

let currentUserId: number | null = null;

export function setCurrentUserId(id: number | null): void {
  currentUserId = id;
}

async function jsonFetch<T>(url: string, init?: RequestInit, requireUser = false): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (currentUserId != null) headers.set("X-User-Id", String(currentUserId));
  if (requireUser && currentUserId == null) {
    throw new Error("not signed in");
  }
  const resp = await fetch(url, { ...init, headers });
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

// User-scoped endpoints
export function getPortfolio(): Promise<Portfolio> {
  return jsonFetch<Portfolio>("/api/portfolio", undefined, true);
}

export function getTrades(limit = 100): Promise<TradeRow[]> {
  return jsonFetch<TradeRow[]>(`/api/trades?limit=${limit}`, undefined, true);
}

export function postTrade(symbol: string, side: "BUY" | "SELL", quantity: number) {
  return jsonFetch<{ trade_id: number; price_cents: number; realized_pnl_cents: number | null }>(
    "/api/trades",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, side, quantity }),
    },
    true,
  );
}

// Public endpoints (no user header required, but sent if present)
export function getQuote(symbol: string): Promise<Quote> {
  return jsonFetch<Quote>(`/api/quote/${encodeURIComponent(symbol)}`);
}

export function getHistory(symbol: string, range: RangeLabel): Promise<HistoryResponse> {
  return jsonFetch<HistoryResponse>(
    `/api/history/${encodeURIComponent(symbol)}?range=${encodeURIComponent(range)}`,
  );
}

export function searchSymbols(q: string, signal?: AbortSignal): Promise<SearchResponse> {
  return jsonFetch<SearchResponse>(`/api/search?q=${encodeURIComponent(q)}`, { signal });
}

// User management
export function listUsers(): Promise<User[]> {
  return jsonFetch<User[]>("/api/users");
}

export function createUser(name: string, startingCashCents: number): Promise<User> {
  return jsonFetch<User>("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, starting_cash_cents: startingCashCents }),
  });
}
