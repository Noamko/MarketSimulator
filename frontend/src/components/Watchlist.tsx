import { useEffect, useRef, useState } from "react";
import type { SearchResult, Tick } from "../types";
import { fmtMoney, fmtSignedMoney, fmtPct } from "../format";
import { searchSymbols } from "../api";

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
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  // Debounced search on input change.
  useEffect(() => {
    const q = input.trim();
    if (!q) { setResults([]); setLoading(false); return; }
    setLoading(true);
    const ctrl = new AbortController();
    const id = setTimeout(() => {
      searchSymbols(q, ctrl.signal)
        .then((r) => { setResults(r.results); setHighlight(0); })
        .catch((e) => { if (e?.name !== "AbortError") setResults([]); })
        .finally(() => setLoading(false));
    }, 250);
    return () => { clearTimeout(id); ctrl.abort(); };
  }, [input]);

  // Close dropdown on outside click.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const pick = (sym: string) => {
    const s = sym.trim().toUpperCase();
    if (!s) return;
    if (!symbols.includes(s)) onAdd(s);
    onSelect(s);
    setInput("");
    setResults([]);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || results.length === 0) {
      if (e.key === "Enter") { e.preventDefault(); pick(input); }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => (h + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => (h - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      pick(results[highlight].symbol);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="panel watchlist">
      <h2>Watchlist</h2>
      {symbols.map((sym) => {
        const tick = prices[sym];
        const prev = tick?.prev_close_cents ?? null;
        const change = tick && prev != null ? tick.price_cents - prev : null;
        const changeCls = change == null ? "muted" : change > 0 ? "positive" : change < 0 ? "negative" : "muted";
        return (
          <div
            key={sym}
            className={`row ${selected === sym ? "active" : ""}`}
            onClick={() => onSelect(sym)}
          >
            <div className="row-left">
              <div className="sym">{sym}</div>
              <div className={`row-change ${changeCls}`}>
                {change == null
                  ? <span className="muted">—</span>
                  : <>
                      <span>{fmtSignedMoney(change)}</span>
                      <span className="muted">·</span>
                      <span>{fmtPct(change, prev ?? 1)}</span>
                    </>}
              </div>
            </div>
            <div className="row-right">
              <div className="price">
                {tick ? fmtMoney(tick.price_cents) : <span className="muted">…</span>}
              </div>
              <button
                className="remove"
                onClick={(e) => { e.stopPropagation(); onRemove(sym); }}
                title="Remove"
              >×</button>
            </div>
          </div>
        );
      })}
      <div className="add-wrap" ref={wrapRef}>
        <div className="add">
          <input
            placeholder="Search ticker or company"
            value={input}
            onChange={(e) => { setInput(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
            maxLength={40}
            autoComplete="off"
          />
          <button type="button" onClick={() => pick(input)}>Add</button>
        </div>
        {open && input.trim() && (
          <div className="dropdown">
            {loading && results.length === 0 && (
              <div className="dropdown-row muted">Searching…</div>
            )}
            {!loading && results.length === 0 && (
              <div className="dropdown-row muted">No matches</div>
            )}
            {results.map((r, i) => (
              <div
                key={r.symbol}
                className={`dropdown-row ${i === highlight ? "highlight" : ""}`}
                onMouseDown={(e) => { e.preventDefault(); pick(r.symbol); }}
                onMouseEnter={() => setHighlight(i)}
              >
                <span className="ds-sym">{r.symbol}</span>
                <span className="ds-desc">{r.description}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
