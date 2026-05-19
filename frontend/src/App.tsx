import { useCallback, useEffect, useMemo, useState } from "react";
import { MarketStatus } from "./components/MarketStatus";
import { Watchlist } from "./components/Watchlist";
import { PriceChart } from "./components/PriceChart";
import { TimeframeBar } from "./components/TimeframeBar";
import { TradeForm } from "./components/TradeForm";
import { Portfolio } from "./components/Portfolio";
import { TradeHistory } from "./components/TradeHistory";
import { useMarketSocket } from "./hooks/useMarketSocket";
import { getPortfolio, getTrades } from "./api";
import type { Portfolio as PortfolioT, RangeLabel, TradeRow } from "./types";

const DEFAULT_SYMBOLS = ["AAPL", "MSFT", "TSLA", "NVDA", "SPY"];
const WATCHLIST_KEY = "marketsim.watchlist";

function loadWatchlist(): string[] {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr) && arr.every((x) => typeof x === "string")) return arr;
    }
  } catch { /* ignore */ }
  return DEFAULT_SYMBOLS;
}

export default function App() {
  const [watchlist, setWatchlist] = useState<string[]>(loadWatchlist);
  const [selected, setSelected] = useState<string | null>(() => loadWatchlist()[0] ?? null);
  const [portfolio, setPortfolio] = useState<PortfolioT | null>(null);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [range, setRange] = useState<RangeLabel>("Sec");

  const symbols = useMemo(() => watchlist, [watchlist]);
  const { prices, connected, onTick } = useMarketSocket(symbols);

  useEffect(() => {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist));
  }, [watchlist]);

  const refresh = useCallback(async () => {
    const [p, t] = await Promise.all([getPortfolio(), getTrades(100)]);
    setPortfolio(p);
    setTrades(t);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // Refresh portfolio every 2s so unrealized P&L tracks the live ticks.
  useEffect(() => {
    const id = setInterval(() => { void getPortfolio().then(setPortfolio).catch(() => {}); }, 2000);
    return () => clearInterval(id);
  }, []);

  const addSymbol = (sym: string) => setWatchlist((cur) => cur.includes(sym) ? cur : [...cur, sym]);
  const removeSymbol = (sym: string) => {
    setWatchlist((cur) => cur.filter((s) => s !== sym));
    setSelected((cur) => (cur === sym ? null : cur));
  };

  const selectedTick = selected ? prices[selected] : undefined;

  return (
    <div className="app">
      <div className="header">
        <h1>MarketSimulator</h1>
        <MarketStatus open={portfolio?.market_open ?? false} connected={connected} />
      </div>
      <div className="grid">
        <Watchlist
          symbols={watchlist}
          prices={prices}
          selected={selected}
          onSelect={setSelected}
          onAdd={addSymbol}
          onRemove={removeSymbol}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <TimeframeBar value={range} onChange={setRange} />
            <PriceChart symbol={selected} prices={prices} onTick={onTick} range={range} />
          </div>
          <Portfolio data={portfolio} onPick={(s) => { addSymbol(s); setSelected(s); }} />
          <TradeHistory trades={trades} />
        </div>
        <TradeForm
          symbol={selected}
          tick={selectedTick}
          cashCents={portfolio?.cash_cents ?? 0}
          onTraded={refresh}
        />
      </div>
    </div>
  );
}
