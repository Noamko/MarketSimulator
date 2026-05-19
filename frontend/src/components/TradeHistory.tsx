import type { TradeRow } from "../types";
import { fmtMoney, fmtSignedMoney } from "../format";

interface Props { trades: TradeRow[]; }

export function TradeHistory({ trades }: Props) {
  return (
    <div className="panel">
      <h2>Trade history</h2>
      {trades.length === 0 ? (
        <div className="muted" style={{ fontSize: 13 }}>No trades yet.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Side</th>
              <th>Symbol</th>
              <th className="num">Qty</th>
              <th className="num">Price</th>
              <th className="num">Realized P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => {
              const when = t.executed_at.replace("T", " ").slice(0, 19);
              const pnlCls = t.realized_pnl_cents == null
                ? "muted"
                : t.realized_pnl_cents > 0 ? "positive" : t.realized_pnl_cents < 0 ? "negative" : "";
              return (
                <tr key={t.id}>
                  <td className="muted">{when}</td>
                  <td className={t.side === "BUY" ? "side-buy" : "side-sell"}>{t.side}</td>
                  <td><strong>{t.symbol}</strong></td>
                  <td className="num">{t.quantity}</td>
                  <td className="num">{fmtMoney(t.price_cents)}</td>
                  <td className={`num ${pnlCls}`}>
                    {t.realized_pnl_cents == null ? "—" : fmtSignedMoney(t.realized_pnl_cents)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
