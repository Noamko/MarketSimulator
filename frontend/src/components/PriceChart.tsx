import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { RangeLabel, Tick } from "../types";
import { fmtMoney } from "../format";
import { getHistory } from "../api";

interface Props {
  symbol: string | null;
  prices: Record<string, Tick>;
  onTick: (cb: (t: Tick) => void) => () => void;
  range: RangeLabel;
}

export function PriceChart({ symbol, prices, onTick, range }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const lastTsRef = useRef<number>(0);
  const loadIdRef = useRef<number>(0);
  const statusRef = useRef<HTMLDivElement | null>(null);
  const setStatus = (text: string) => {
    if (statusRef.current) statusRef.current.textContent = text;
  };

  // Create chart once.
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b949e",
      },
      grid: {
        vertLines: { color: "#1c2230" },
        horzLines: { color: "#1c2230" },
      },
      rightPriceScale: { borderColor: "#2a3142" },
      timeScale: { borderColor: "#2a3142", timeVisible: true, secondsVisible: true },
      height: 380,
    });
    const series = chart.addLineSeries({ color: "#58a6ff", lineWidth: 2 });
    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Load history (or seed live view) whenever symbol or range changes.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    series.setData([]);
    lastTsRef.current = 0;
    if (!symbol) {
      setStatus("");
      return;
    }

    const myLoad = ++loadIdRef.current;
    if (range === "Sec") {
      // Live mode: seed from cache (if any), then ticks arrive via the onTick effect.
      const tick = prices[symbol];
      if (tick) {
        const t = (tick.timestamp_ms > 0
          ? Math.floor(tick.timestamp_ms / 1000)
          : Math.floor(Date.now() / 1000)) as UTCTimestamp;
        series.update({ time: t, value: tick.price_cents / 100 });
        lastTsRef.current = t as number;
        setStatus("Live (since you opened)");
      } else {
        setStatus("Waiting for first tick…");
      }
      return;
    }

    setStatus(`Loading ${range}…`);
    getHistory(symbol, range)
      .then((resp) => {
        if (myLoad !== loadIdRef.current) return; // a newer request superseded us
        const data = resp.points.map((p) => ({
          time: Math.floor(p.timestamp_ms / 1000) as UTCTimestamp,
          value: p.price_cents / 100,
        }));
        seriesRef.current?.setData(data);
        if (data.length > 0) {
          lastTsRef.current = data[data.length - 1].time as number;
          chartRef.current?.timeScale().fitContent();
          setStatus(`${data.length} pts · ${range}`);
        } else {
          setStatus(`No data for ${range} (market may be closed)`);
        }
      })
      .catch((e) => {
        if (myLoad !== loadIdRef.current) return;
        setStatus(`Error: ${e?.message ?? e}`);
      });
  }, [symbol, range]); // eslint-disable-line react-hooks/exhaustive-deps

  // Live ticks only in Sec mode.
  useEffect(() => {
    if (!symbol || range !== "Sec") return;
    const unsubscribe = onTick((tick) => {
      if (tick.symbol !== symbol || !seriesRef.current) return;
      let t = tick.timestamp_ms > 0 ? Math.floor(tick.timestamp_ms / 1000) : Math.floor(Date.now() / 1000);
      if (t <= lastTsRef.current) t = lastTsRef.current + 1;
      lastTsRef.current = t;
      seriesRef.current.update({ time: t as UTCTimestamp, value: tick.price_cents / 100 });
    });
    return unsubscribe;
  }, [symbol, range, onTick]);

  const current = symbol ? prices[symbol] : undefined;

  return (
    <div className="panel">
      <div className="chart-header">
        <h2 style={{ margin: 0 }}>{symbol ?? "Pick a symbol"}</h2>
        <div className="current-price">{current ? fmtMoney(current.price_cents) : "—"}</div>
      </div>
      <div className="chart-wrap">
        <div ref={containerRef} style={{ height: 380 }} />
        {!symbol && <div className="empty">Select a symbol from the watchlist</div>}
      </div>
      <div ref={statusRef} className="chart-status muted" />
    </div>
  );
}
