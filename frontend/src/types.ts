export interface Position {
  symbol: string;
  quantity: number;
  avg_cost_cents: number;
  last_price_cents: number | null;
  market_value_cents: number | null;
  unrealized_pnl_cents: number | null;
}

export interface Portfolio {
  cash_cents: number;
  positions: Position[];
  total_realized_pnl_cents: number;
  total_equity_cents: number;
  market_open: boolean;
}

export interface TradeRow {
  id: number;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price_cents: number;
  executed_at: string;
  realized_pnl_cents: number | null;
}

export interface Tick {
  symbol: string;
  price_cents: number;
  timestamp_ms: number;
  source: "stream" | "rest";
  prev_close_cents: number | null;
}

export interface Quote {
  symbol: string;
  price_cents: number;
  source: "stream" | "rest";
  timestamp_ms: number | null;
}

export type RangeLabel =
  | "Sec" | "Min" | "Hour" | "Day" | "Week"
  | "Month" | "Year" | "2Y" | "5Y" | "10Y";

export const ALL_RANGES: RangeLabel[] = [
  "Sec", "Min", "Hour", "Day", "Week", "Month", "Year", "2Y", "5Y", "10Y",
];

export interface HistoryPoint {
  timestamp_ms: number;
  price_cents: number;
}

export interface HistoryResponse {
  symbol: string;
  range: RangeLabel;
  points: HistoryPoint[];
}

export interface SearchResult {
  symbol: string;
  description: string;
  type: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

export interface User {
  id: number;
  name: string;
  cash_cents: number;
  created_at: string;
}

export type WebhookEvent =
  | "PRICE_TARGET" | "MARKET_STATUS" | "TRADE_EXECUTED" | "PORTFOLIO_THRESHOLD";

export type WebhookDirection = "above" | "below";
export type WebhookMetric = "equity" | "realized_pnl";

export interface Webhook {
  id: number;
  user_id: number;
  url: string;
  event_type: WebhookEvent;
  symbol: string | null;
  target_cents: number | null;
  direction: string | null;
  metric: string | null;
  enabled: boolean;
  one_shot: boolean;
  last_fired_at: string | null;
  created_at: string;
}

export interface WebhookCreate {
  url: string;
  event_type: WebhookEvent;
  symbol?: string | null;
  target_cents?: number | null;
  direction?: WebhookDirection | null;
  metric?: WebhookMetric | null;
  one_shot?: boolean;
}
