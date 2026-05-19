import { useState } from "react";
import type { Tick } from "../types";
import { postTrade } from "../api";
import { fmtMoney } from "../format";

interface Props {
  symbol: string | null;
  tick: Tick | undefined;
  cashCents: number;
  onTraded: () => void;
}

export function TradeForm({ symbol, tick, cashCents, onTraded }: Props) {
  const [qty, setQty] = useState<string>("1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const quantity = Math.max(0, Math.floor(Number(qty) || 0));
  const estCost = tick && quantity > 0 ? tick.price_cents * quantity : null;

  const trade = async (side: "BUY" | "SELL") => {
    if (!symbol || quantity <= 0) return;
    setBusy(true);
    setError(null);
    try {
      await postTrade(symbol, side, quantity);
      onTraded();
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  const disabled = !symbol || !tick || quantity <= 0 || busy;

  return (
    <div className="panel">
      <h2>Place order</h2>
      <div className="trade-form">
        <div className="row">
          <label>Symbol</label>
          <input value={symbol ?? ""} readOnly placeholder="Select from watchlist" />
        </div>
        <div className="row">
          <label>Quantity</label>
          <input
            type="number"
            min={1}
            step={1}
            value={qty}
            onChange={(e) => setQty(e.target.value)}
          />
        </div>
        <div className="estimate">
          {estCost != null
            ? `Est: ${fmtMoney(estCost)} @ ${fmtMoney(tick!.price_cents)} · Cash: ${fmtMoney(cashCents)}`
            : `Cash: ${fmtMoney(cashCents)}`}
        </div>
        <div className="actions">
          <button className="buy" disabled={disabled} onClick={() => trade("BUY")}>Buy</button>
          <button className="sell" disabled={disabled} onClick={() => trade("SELL")}>Sell</button>
        </div>
        <div className="error">{error}</div>
      </div>
    </div>
  );
}
