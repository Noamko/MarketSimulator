import { useState } from "react";
import type { Tick } from "../types";
import { fmtMoney } from "../format";

interface Props {
  symbols: string[];
  prices: Record<string, Tick>;
  selected: string | null;
  onSelect: (sym: string) => void;
  onAdd: (sym: string) => void;
  onRemove: (sym: string) => void;
}

export function Watchlist({ symbols, prices, selected, onSelect, onAdd, onRemove }: Props) {
  const [input, setInput] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const sym = input.trim().toUpperCase();
    if (sym && !symbols.includes(sym)) onAdd(sym);
    setInput("");
  };

  return (
    <div className="panel watchlist">
      <h2>Watchlist</h2>
      {symbols.map((sym) => {
        const tick = prices[sym];
        return (
          <div
            key={sym}
            className={`row ${selected === sym ? "active" : ""}`}
            onClick={() => onSelect(sym)}
          >
            <span className="sym">{sym}</span>
            <span className="price">
              {tick ? fmtMoney(tick.price_cents) : <span className="muted">…</span>}
              <button
                className="remove"
                onClick={(e) => { e.stopPropagation(); onRemove(sym); }}
                title="Remove"
              >×</button>
            </span>
          </div>
        );
      })}
      <form className="add" onSubmit={submit}>
        <input
          placeholder="Add ticker"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={10}
        />
        <button type="submit">Add</button>
      </form>
    </div>
  );
}
