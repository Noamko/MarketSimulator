import { useCallback, useEffect, useMemo, useState } from "react";
import { LoginScreen } from "./components/LoginScreen";
import { MarketStatus } from "./components/MarketStatus";
import { Watchlist } from "./components/Watchlist";
import { PriceChart } from "./components/PriceChart";
import { TimeframeBar } from "./components/TimeframeBar";
import { TradeForm } from "./components/TradeForm";
import { Portfolio } from "./components/Portfolio";
import { TradeHistory } from "./components/TradeHistory";
import { Settings } from "./components/Settings";
import { useMarketSocket } from "./hooks/useMarketSocket";
import { getPortfolio, getTrades, setCurrentUserId } from "./api";
import type { Portfolio as PortfolioT, RangeLabel, TradeRow, User } from "./types";

const DEFAULT_SYMBOLS = ["AAPL", "MSFT", "TSLA", "NVDA", "SPY"];
const USER_KEY = "marketsim.user";
const watchlistKey = (userId: number) => `marketsim.watchlist.${userId}`;

function loadUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    const u = JSON.parse(raw);
    if (u && typeof u.id === "number" && typeof u.name === "string") return u as User;
  } catch { /* ignore */ }
  return null;
}

function loadWatchlist(userId: number): string[] {
  try {
    const raw = localStorage.getItem(watchlistKey(userId));
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr) && arr.every((x) => typeof x === "string")) return arr;
    }
  } catch { /* ignore */ }
  return DEFAULT_SYMBOLS;
}

export default function App() {
  const [user, setUser] = useState<User | null>(() => {
    const u = loadUser();
    if (u) setCurrentUserId(u.id);
    return u;
  });

  if (!user) {
    return (
      <LoginScreen onPick={(u) => {
        localStorage.setItem(USER_KEY, JSON.stringify(u));
        setCurrentUserId(u.id);
        setUser(u);
      }} />
    );
  }
  return <SignedInApp user={user} onSignOut={() => {
    localStorage.removeItem(USER_KEY);
    setCurrentUserId(null);
    setUser(null);
  }} />;
}

function SignedInApp({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const [watchlist, setWatchlist] = useState<string[]>(() => loadWatchlist(user.id));
  const [selected, setSelected] = useState<string | null>(() => loadWatchlist(user.id)[0] ?? null);
  const [portfolio, setPortfolio] = useState<PortfolioT | null>(null);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [range, setRange] = useState<RangeLabel>("Sec");
  const [view, setView] = useState<"dashboard" | "settings">("dashboard");

  const symbols = useMemo(() => watchlist, [watchlist]);
  const { prices, connected, onTick } = useMarketSocket(symbols);

  useEffect(() => {
    localStorage.setItem(watchlistKey(user.id), JSON.stringify(watchlist));
  }, [watchlist, user.id]);

  const refresh = useCallback(async () => {
    const [p, t] = await Promise.all([getPortfolio(), getTrades(100)]);
    setPortfolio(p);
    setTrades(t);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

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
  const selectedPosition = selected
    ? portfolio?.positions.find((p) => p.symbol === selected) ?? null
    : null;

  return (
    <div className="app">
      <div className="header">
        <h1>MarketSimulator</h1>
        <div className="header-right">
          <MarketStatus open={portfolio?.market_open ?? false} connected={connected} />
          <button
            type="button"
            className={`nav-btn${view === "settings" ? " active" : ""}`}
            onClick={() => setView((v) => (v === "settings" ? "dashboard" : "settings"))}
          >
            {view === "settings" ? "← Dashboard" : "⚙ Settings"}
          </button>
          <span className="user-chip">
            <span className="muted">user</span>{" "}
            <strong>{user.name}</strong>
            <button type="button" className="link-btn" onClick={onSignOut}>switch</button>
          </span>
        </div>
      </div>
      {view === "settings" ? <Settings /> : (
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
            <PriceChart
              symbol={selected}
              prices={prices}
              onTick={onTick}
              range={range}
              position={selectedPosition}
            />
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
      )}
    </div>
  );
}
