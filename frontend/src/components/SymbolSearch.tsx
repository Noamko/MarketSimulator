import { useEffect, useRef, useState } from "react";
import type { SearchResult } from "../types";
import { searchSymbols } from "../api";

interface Props {
  value: string;
  onChange: (sym: string) => void;
  placeholder?: string;
}

/** Ticker/company search box with a debounced suggestions dropdown.
 *  Controlled by `value`; calls `onChange` on typing and on picking a result. */
export function SymbolSearch({ value, onChange, placeholder }: Props) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  // Debounced search on value change.
  useEffect(() => {
    const q = value.trim();
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
  }, [value]);

  // Close dropdown on outside click.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const pick = (sym: string) => {
    onChange(sym.trim().toUpperCase());
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || results.length === 0) return;
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
    <div className="symbol-search" ref={wrapRef}>
      <input
        value={value}
        placeholder={placeholder ?? "Search ticker or company"}
        onChange={(e) => { onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        maxLength={40}
        autoComplete="off"
      />
      {open && value.trim() && (
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
  );
}
