import type { Portfolio as PortfolioT } from "../types";
import { fmtMoney, fmtSignedMoney, fmtPct } from "../format";

interface Props {
  data: PortfolioT | null;
  onPick: (sym: string) => void;
}

export function Portfolio({ data, onPick }: Props) {
  if (!data) return <div className="panel"><h2>Portfolio</h2><div className="muted">Loading…</div></div>;

  const unrealized = data.positions.reduce(
    (sum, p) => sum + (p.unrealized_pnl_cents ?? 0),
    0,
  );

  return (
    <div className="panel">
      <h2>Portfolio</h2>
      <div className="totals">
        <div className="cell">
          <div className="label">Equity</div>
          <div className="value">{fmtMoney(data.total_equity_cents)}</div>
        </div>
        <div className="cell">
          <div className="label">Cash</div>
          <div className="value">{fmtMoney(data.cash_cents)}</div>
        </div>
        <div className="cell">
          <div className="label">Unrealized P&amp;L</div>
          <div className={`value ${unrealized > 0 ? "positive" : unrealized < 0 ? "negative" : ""}`}>
            {fmtSignedMoney(unrealized)}
          </div>
        </div>
        <div className="cell">
          <div className="label">Realized P&amp;L</div>
          <div className={`value ${data.total_realized_pnl_cents > 0 ? "positive" : data.total_realized_pnl_cents < 0 ? "negative" : ""}`}>
            {fmtSignedMoney(data.total_realized_pnl_cents)}
          </div>
        </div>
      </div>

      {data.positions.length === 0 ? (
        <div className="muted" style={{ fontSize: 13 }}>No open positions.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th className="num">Qty</th>
              <th className="num">Avg cost</th>
              <th className="num">Last</th>
              <th className="num">Value</th>
              <th className="num">P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {data.positions.map((p) => {
              const pnl = p.unrealized_pnl_cents;
              const cls = pnl == null ? "muted" : pnl > 0 ? "positive" : pnl < 0 ? "negative" : "";
              const pct = p.last_price_cents != null
                ? fmtPct(p.last_price_cents - p.avg_cost_cents, p.avg_cost_cents)
                : "—";
              return (
                <tr key={p.symbol} onClick={() => onPick(p.symbol)} style={{ cursor: "pointer" }}>
                  <td><strong>{p.symbol}</strong></td>
                  <td className="num">{p.quantity}</td>
                  <td className="num">{fmtMoney(p.avg_cost_cents)}</td>
                  <td className="num">{fmtMoney(p.last_price_cents)}</td>
                  <td className="num">{fmtMoney(p.market_value_cents)}</td>
                  <td className={`num ${cls}`}>{fmtSignedMoney(pnl)} <span className="muted">({pct})</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
