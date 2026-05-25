import { useEffect, useState } from "react";
import type { Webhook, WebhookCreate, WebhookEvent } from "../types";
import { listWebhooks, createWebhook, updateWebhook, deleteWebhook } from "../api";
import { fmtMoney } from "../format";
import { SymbolSearch } from "./SymbolSearch";

const EVENT_LABELS: Record<WebhookEvent, string> = {
  PRICE_TARGET: "Price target hit",
  MARKET_STATUS: "Market opens / closes",
  TRADE_EXECUTED: "Trade executed",
  PORTFOLIO_THRESHOLD: "Portfolio threshold",
};

function describe(w: Webhook): string {
  switch (w.event_type) {
    case "PRICE_TARGET":
      return `${w.symbol} ${w.direction} ${fmtMoney(w.target_cents ?? 0)}`;
    case "PORTFOLIO_THRESHOLD":
      return `${w.metric === "equity" ? "Equity" : "Realized P&L"} ${w.direction} ${fmtMoney(w.target_cents ?? 0)}`;
    case "MARKET_STATUS":
      return "On open and close";
    case "TRADE_EXECUTED":
      return "On every buy / sell";
  }
}

export function Settings() {
  const [hooks, setHooks] = useState<Webhook[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // form state
  const [eventType, setEventType] = useState<WebhookEvent>("PRICE_TARGET");
  const [url, setUrl] = useState("");
  const [symbol, setSymbol] = useState("");
  const [target, setTarget] = useState("");
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [metric, setMetric] = useState<"equity" | "realized_pnl">("equity");
  const [oneShot, setOneShot] = useState(true);

  const reload = async () => {
    try {
      setHooks(await listWebhooks());
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  };

  useEffect(() => { void reload(); }, []);

  const needsTarget = eventType === "PRICE_TARGET" || eventType === "PORTFOLIO_THRESHOLD";

  const submit = async () => {
    setError(null);
    const body: WebhookCreate = { url: url.trim(), event_type: eventType, one_shot: oneShot };
    if (eventType === "PRICE_TARGET") {
      body.symbol = symbol.trim().toUpperCase();
      body.target_cents = Math.round(Number(target) * 100);
      body.direction = direction;
    } else if (eventType === "PORTFOLIO_THRESHOLD") {
      body.metric = metric;
      body.target_cents = Math.round(Number(target) * 100);
      body.direction = direction;
    }
    setBusy(true);
    try {
      await createWebhook(body);
      setUrl(""); setSymbol(""); setTarget("");
      await reload();
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (w: Webhook) => {
    try {
      await updateWebhook(w.id, !w.enabled);
      await reload();
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  };

  const remove = async (w: Webhook) => {
    try {
      await deleteWebhook(w.id);
      await reload();
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  };

  const urlValid = /^https?:\/\//.test(url.trim());
  const targetValid = !needsTarget || Number(target) > 0;
  const symbolValid = eventType !== "PRICE_TARGET" || symbol.trim().length > 0;
  const canSubmit = urlValid && targetValid && symbolValid && !busy;

  return (
    <div style={{ maxWidth: 760 }}>
      <div className="panel" style={{ marginBottom: 16 }}>
        <h2>New webhook</h2>
        <div className="trade-form">
          <div className="row">
            <label>Event</label>
            <select value={eventType} onChange={(e) => setEventType(e.target.value as WebhookEvent)} style={{ flex: 1 }}>
              {(Object.keys(EVENT_LABELS) as WebhookEvent[]).map((ev) => (
                <option key={ev} value={ev}>{EVENT_LABELS[ev]}</option>
              ))}
            </select>
          </div>

          {eventType === "PRICE_TARGET" && (
            <div className="row">
              <label>Symbol</label>
              <SymbolSearch value={symbol} onChange={setSymbol} placeholder="Search ticker or company" />
            </div>
          )}

          {eventType === "PORTFOLIO_THRESHOLD" && (
            <div className="row">
              <label>Metric</label>
              <select value={metric} onChange={(e) => setMetric(e.target.value as any)} style={{ flex: 1 }}>
                <option value="equity">Total equity</option>
                <option value="realized_pnl">Realized P&amp;L</option>
              </select>
            </div>
          )}

          {needsTarget && (
            <div className="row">
              <label>When</label>
              <select value={direction} onChange={(e) => setDirection(e.target.value as any)}>
                <option value="above">rises above</option>
                <option value="below">drops below</option>
              </select>
              <input
                type="number" step="0.01" value={target}
                onChange={(e) => setTarget(e.target.value)} placeholder="$ amount" style={{ flex: 1 }}
              />
            </div>
          )}

          <div className="row">
            <label>POST to</label>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/hook" />
          </div>

          <div className="row">
            <label>Fire once</label>
            <input type="checkbox" checked={oneShot} onChange={(e) => setOneShot(e.target.checked)} style={{ flex: "none" }} />
            <span className="muted" style={{ fontSize: 12 }}>
              {eventType === "MARKET_STATUS" || eventType === "TRADE_EXECUTED"
                ? "(ignored for this event — fires every time)"
                : "disable the rule after it fires once"}
            </span>
          </div>

          <div className="actions">
            <button className="buy" disabled={!canSubmit} onClick={submit}>Create webhook</button>
          </div>
          <div className="error">{error}</div>
        </div>
      </div>

      <div className="panel">
        <h2>Your webhooks</h2>
        {hooks.length === 0 ? (
          <p className="muted">No webhooks yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Event</th><th>Condition</th><th>URL</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {hooks.map((w) => (
                <tr key={w.id}>
                  <td>{EVENT_LABELS[w.event_type]}</td>
                  <td>{describe(w)}</td>
                  <td className="muted" style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{w.url}</td>
                  <td className={w.enabled ? "positive" : "muted"}>
                    {w.enabled ? "active" : "off"}
                    {w.last_fired_at && <span className="muted" style={{ fontSize: 11 }}> · fired</span>}
                  </td>
                  <td className="num">
                    <button className="link-btn" onClick={() => toggle(w)}>{w.enabled ? "disable" : "enable"}</button>
                    <button className="link-btn" onClick={() => remove(w)}>delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
