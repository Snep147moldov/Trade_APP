"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  IChartApi,
  ISeriesApi,
  LineSeries,
  LineStyle,
  MouseEventParams,
  UTCTimestamp,
  createChart,
} from "lightweight-charts";
import type { Analysis, PatternsResult } from "@/lib/api";
import { toLocalTime } from "@/lib/api";

const UP = "#34c759";
const DOWN = "#ff3b30";

// ------------------------------- manual drawings (persisted per symbol+tf)

export type DrawMode = "none" | "trend" | "hline";

interface DrawingPoint {
  time: number; // chart-local epoch seconds
  price: number;
}

interface Drawing {
  type: "trend" | "hline";
  p1: DrawingPoint;
  p2?: DrawingPoint;
}

const drawKey = (instrument: string, tf: string) => `cnx_draw:${instrument}:${tf}`;

function loadDrawings(instrument: string, tf: string): Drawing[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(drawKey(instrument, tf)) ?? "[]");
  } catch {
    return [];
  }
}

function saveDrawings(instrument: string, tf: string, items: Drawing[]) {
  localStorage.setItem(drawKey(instrument, tf), JSON.stringify(items));
}

export interface ChartToggles {
  bb: boolean;
  vwap: boolean;
  ichimoku: boolean;
  levels: boolean; // S/R zones + trendlines from pattern engine
  fib: boolean;
  rsi: boolean;
  macd: boolean;
  stoch: boolean;
}

export const DEFAULT_TOGGLES: ChartToggles = {
  bb: false, vwap: false, ichimoku: false, levels: true, fib: false,
  rsi: false, macd: false, stoch: false,
};

const baseOptions = {
  layout: {
    background: { type: ColorType.Solid, color: "transparent" },
    textColor: "#8e8e93",
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif",
    attributionLogo: false,
  },
  grid: {
    vertLines: { color: "rgba(0,0,0,0.04)" },
    horzLines: { color: "rgba(0,0,0,0.04)" },
  },
  rightPriceScale: { borderVisible: false },
  timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
  crosshair: {
    vertLine: { color: "rgba(0,0,0,0.2)", labelBackgroundColor: "#1c1c1e" },
    horzLine: { color: "rgba(0,0,0,0.2)", labelBackgroundColor: "#1c1c1e" },
  },
  autoSize: true,
} as const;

const lineOpts = (color: string, width = 1, style?: LineStyle) => ({
  color,
  lineWidth: width as 1 | 2 | 3 | 4,
  lineStyle: style,
  priceLineVisible: false,
  lastValueVisible: false,
  crosshairMarkerVisible: false,
});

function seriesData(candles: Analysis["candles"], values: (number | null)[]) {
  return candles
    .map((c, i) => ({ time: toLocalTime(c.time) as UTCTimestamp, value: values[i] }))
    .filter((p): p is { time: UTCTimestamp; value: number } => p.value != null);
}

/** Sub-pane chart (RSI / MACD / Stochastic) synchronized visually by data range. */
function IndicatorPane({ analysis, kind }: { analysis: Analysis; kind: "rsi" | "macd" | "stoch" }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = createChart(el, { ...baseOptions, height: 110 });
    const o = analysis.overlays;
    if (kind === "rsi") {
      const s = chart.addSeries(LineSeries, lineOpts("#af52de", 1));
      s.setData(seriesData(analysis.candles, o.rsi));
      s.createPriceLine({ price: 70, color: "rgba(255,59,48,0.4)", lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "" });
      s.createPriceLine({ price: 30, color: "rgba(52,199,89,0.4)", lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "" });
    } else if (kind === "macd") {
      const hist = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false });
      hist.setData(
        analysis.candles
          .map((c, i) => ({
            time: toLocalTime(c.time) as UTCTimestamp,
            value: o.macd_hist[i],
            color: (o.macd_hist[i] ?? 0) >= 0 ? "rgba(52,199,89,0.5)" : "rgba(255,59,48,0.5)",
          }))
          .filter((p): p is { time: UTCTimestamp; value: number; color: string } => p.value != null)
      );
      chart.addSeries(LineSeries, lineOpts("#0a84ff", 1)).setData(seriesData(analysis.candles, o.macd));
      chart.addSeries(LineSeries, lineOpts("#ff9f0a", 1)).setData(seriesData(analysis.candles, o.macd_signal));
    } else {
      chart.addSeries(LineSeries, lineOpts("#0a84ff", 1)).setData(seriesData(analysis.candles, o.stoch_k));
      chart.addSeries(LineSeries, lineOpts("#ff9f0a", 1)).setData(seriesData(analysis.candles, o.stoch_d));
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [analysis, kind]);

  const label = kind === "rsi" ? "RSI 14" : kind === "macd" ? "MACD 12/26/9" : "Stochastic 14/3/3";
  return (
    <div>
      <p className="mt-1 px-1 text-[10px] text-muted-foreground">{label}</p>
      <div ref={ref} className="h-[110px] w-full" />
    </div>
  );
}

const TF_SEC: Record<string, number> = {
  "1m": 60, "5m": 300, "15m": 900, "40m": 2400,
  "1h": 3600, "4h": 14400, "1d": 86400,
};

interface LiveBar {
  time: number; open: number; high: number; low: number; close: number;
}

export function PriceChart({
  analysis,
  patterns,
  toggles = DEFAULT_TOGGLES,
  livePrice,
  drawMode = "none",
  drawVersion = 0,
  onDrawingAdded,
}: {
  analysis: Analysis | null;
  patterns?: PatternsResult | null;
  toggles?: ChartToggles;
  livePrice?: number | null;
  drawMode?: DrawMode;
  drawVersion?: number;
  onDrawingAdded?: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lastBarRef = useRef<LiveBar | null>(null);
  const modeRef = useRef<DrawMode>(drawMode);
  const pendingRef = useRef<DrawingPoint | null>(null);
  const [pendingVisible, setPendingVisible] = useState(false);
  modeRef.current = drawMode;

  // live tick: extend/roll the last candle in place — no chart rebuild,
  // so the bar visibly moves between the 30s full analysis refreshes
  useEffect(() => {
    const series = candleSeriesRef.current;
    const last = lastBarRef.current;
    if (!series || !last || livePrice == null || !analysis) return;
    const gran = TF_SEC[analysis.timeframe] ?? 3600;
    const nowBar = toLocalTime(Math.floor(Date.now() / 1000 / gran) * gran);
    let bar: LiveBar;
    if (nowBar > last.time) {
      bar = { time: nowBar, open: livePrice, high: livePrice, low: livePrice, close: livePrice };
    } else {
      bar = { ...last, close: livePrice,
              high: Math.max(last.high, livePrice), low: Math.min(last.low, livePrice) };
    }
    lastBarRef.current = bar;
    series.update({ time: bar.time as UTCTimestamp, open: bar.open,
                    high: bar.high, low: bar.low, close: bar.close });
  }, [livePrice, analysis]);

  useEffect(() => {
    // leaving draw mode discards a half-finished trendline
    if (drawMode === "none") {
      pendingRef.current = null;
      setPendingVisible(false);
    }
  }, [drawMode]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !analysis) return;

    const chart = createChart(el, { ...baseOptions, height: 420 });
    chartRef.current = chart;
    const o = analysis.overlays;

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP, downColor: DOWN, wickUpColor: UP, wickDownColor: DOWN,
      borderVisible: false,
    });
    candles.setData(
      analysis.candles.map((c) => ({
        time: toLocalTime(c.time) as UTCTimestamp,
        open: c.open, high: c.high, low: c.low, close: c.close,
      }))
    );
    candleSeriesRef.current = candles;
    const lastC = analysis.candles[analysis.candles.length - 1];
    lastBarRef.current = lastC
      ? { time: toLocalTime(lastC.time), open: lastC.open, high: lastC.high,
          low: lastC.low, close: lastC.close }
      : null;

    // ---------------- manual drawings: render saved + capture clicks
    const drawings = loadDrawings(analysis.instrument, analysis.timeframe);
    for (const d of drawings) {
      if (d.type === "hline") {
        candles.createPriceLine({
          price: d.p1.price, color: "#5856d6", lineWidth: 1,
          lineStyle: LineStyle.Solid, axisLabelVisible: true, title: "линия",
        });
      } else if (d.type === "trend" && d.p2) {
        const pts = [d.p1, d.p2].sort((a, b) => a.time - b.time);
        if (pts[0].time !== pts[1].time) {
          chart.addSeries(LineSeries, lineOpts("#5856d6", 2))
            .setData(pts.map((p) => ({ time: p.time as UTCTimestamp, value: p.price })));
        }
      }
    }

    const clickHandler = (param: MouseEventParams) => {
      const mode = modeRef.current;
      if (mode === "none" || !param.point) return;
      const price = (candles as ISeriesApi<"Candlestick">).coordinateToPrice(param.point.y);
      const time = (param.time as number | undefined)
        ?? (chart.timeScale().coordinateToTime(param.point.x) as number | null);
      if (price == null || time == null) return;
      const pt: DrawingPoint = { time: time as number, price: price as number };
      const items = loadDrawings(analysis.instrument, analysis.timeframe);
      if (mode === "hline") {
        items.push({ type: "hline", p1: pt });
        saveDrawings(analysis.instrument, analysis.timeframe, items);
        onDrawingAdded?.();
      } else if (mode === "trend") {
        if (!pendingRef.current) {
          pendingRef.current = pt;
          setPendingVisible(true);
        } else {
          items.push({ type: "trend", p1: pendingRef.current, p2: pt });
          pendingRef.current = null;
          setPendingVisible(false);
          saveDrawings(analysis.instrument, analysis.timeframe, items);
          onDrawingAdded?.();
        }
      }
    };
    chart.subscribeClick(clickHandler);

    chart.addSeries(LineSeries, lineOpts("#0a84ff")).setData(seriesData(analysis.candles, o.ema20));
    chart.addSeries(LineSeries, lineOpts("#ff9f0a")).setData(seriesData(analysis.candles, o.ema50));

    if (toggles.bb) {
      chart.addSeries(LineSeries, lineOpts("rgba(88,86,214,0.65)")).setData(seriesData(analysis.candles, o.bb_upper));
      chart.addSeries(LineSeries, lineOpts("rgba(88,86,214,0.35)", 1, LineStyle.Dotted)).setData(seriesData(analysis.candles, o.bb_mid));
      chart.addSeries(LineSeries, lineOpts("rgba(88,86,214,0.65)")).setData(seriesData(analysis.candles, o.bb_lower));
    }
    if (toggles.vwap) {
      chart.addSeries(LineSeries, lineOpts("#af52de", 2)).setData(seriesData(analysis.candles, o.vwap));
    }
    if (toggles.ichimoku) {
      chart.addSeries(LineSeries, lineOpts("rgba(52,199,89,0.8)")).setData(seriesData(analysis.candles, o.ichimoku_tenkan));
      chart.addSeries(LineSeries, lineOpts("rgba(255,59,48,0.8)")).setData(seriesData(analysis.candles, o.ichimoku_kijun));
      chart.addSeries(LineSeries, lineOpts("rgba(52,199,89,0.35)")).setData(seriesData(analysis.candles, o.ichimoku_span_a));
      chart.addSeries(LineSeries, lineOpts("rgba(255,59,48,0.35)")).setData(seriesData(analysis.candles, o.ichimoku_span_b));
    }

    // S/R zones + trendlines + detected pattern lines
    if (toggles.levels && patterns) {
      for (const z of patterns.sr_zones.slice(0, 5)) {
        candles.createPriceLine({
          price: z.price,
          color: z.kind === "support" ? "rgba(52,199,89,0.55)" : "rgba(255,59,48,0.55)",
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: false,
          title: `${z.kind === "support" ? "S" : "R"}·${z.touches}`,
        });
      }
      for (const tl of patterns.trendlines) {
        chart
          .addSeries(LineSeries, lineOpts(
            tl.side === "support" ? "rgba(52,199,89,0.7)" : "rgba(255,59,48,0.7)", 1, LineStyle.Dashed))
          .setData(tl.points.map((p) => ({ time: toLocalTime(p.time) as UTCTimestamp, value: p.price })));
      }
      for (const p of patterns.patterns.slice(0, 4)) {
        if (p.points.length >= 2) {
          chart
            .addSeries(LineSeries, lineOpts("rgba(10,132,255,0.6)", 1, LineStyle.Dashed))
            .setData(
              [...p.points]
                .sort((a, b) => a.time - b.time)
                .filter((pt, i, arr) => i === 0 || pt.time !== arr[i - 1].time)
                .map((pt) => ({ time: toLocalTime(pt.time) as UTCTimestamp, value: pt.price }))
            );
        }
      }
    }

    if (toggles.fib && patterns?.fibonacci) {
      for (const [ratio, price] of Object.entries(patterns.fibonacci.levels)) {
        candles.createPriceLine({
          price,
          color: "rgba(175,82,222,0.45)",
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: true,
          title: `fib ${ratio}`,
        });
      }
    }

    if (analysis.direction !== "HOLD") {
      const lines = [
        { price: analysis.levels.entry, color: "#0a84ff", title: "Вход" },
        { price: analysis.levels.stop_loss, color: DOWN, title: "SL" },
        { price: analysis.levels.take_profit, color: UP, title: "TP" },
      ];
      for (const l of lines) {
        candles.createPriceLine({
          price: l.price, color: l.color, lineWidth: 1,
          lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: l.title,
        });
      }
    }

    chart.timeScale().fitContent();
    return () => {
      chart.unsubscribeClick(clickHandler);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      lastBarRef.current = null;
    };
  }, [analysis, patterns, toggles, drawVersion, onDrawingAdded]);

  return (
    <div className="relative">
      {drawMode !== "none" && (
        <div className="pointer-events-none absolute left-2 top-2 z-10 rounded-lg bg-[#5856d6]/10 px-2 py-1 text-[10px] font-medium text-[#5856d6]">
          {drawMode === "hline"
            ? "Кликните по графику — горизонтальная линия"
            : pendingVisible
              ? "Вторая точка трендлинии…"
              : "Кликните первую точку трендлинии"}
        </div>
      )}
      <div ref={containerRef} className={`h-[420px] w-full ${drawMode !== "none" ? "cursor-crosshair" : ""}`} />
      {analysis && toggles.rsi && <IndicatorPane analysis={analysis} kind="rsi" />}
      {analysis && toggles.macd && <IndicatorPane analysis={analysis} kind="macd" />}
      {analysis && toggles.stoch && <IndicatorPane analysis={analysis} kind="stoch" />}
    </div>
  );
}

export function DrawToolbar({
  instrument,
  timeframe,
  mode,
  onMode,
  onChanged,
}: {
  instrument: string;
  timeframe: string;
  mode: DrawMode;
  onMode: (m: DrawMode) => void;
  onChanged: () => void;
}) {
  const mutate = useCallback((fn: (items: Drawing[]) => Drawing[]) => {
    saveDrawings(instrument, timeframe, fn(loadDrawings(instrument, timeframe)));
    onChanged();
  }, [instrument, timeframe, onChanged]);

  const btn = (active: boolean) =>
    `rounded-lg px-2 py-0.5 text-[11px] transition-colors ${
      active ? "bg-[#5856d6]/15 font-medium text-[#5856d6]"
             : "bg-black/[0.04] text-muted-foreground hover:bg-black/[0.08]"}`;

  return (
    <div className="flex items-center gap-1">
      <span className="mr-1 text-[10px] text-muted-foreground">Рисование:</span>
      <button className={btn(mode === "trend")}
              onClick={() => onMode(mode === "trend" ? "none" : "trend")}>
        ╱ Трендлиния
      </button>
      <button className={btn(mode === "hline")}
              onClick={() => onMode(mode === "hline" ? "none" : "hline")}>
        ─ Уровень
      </button>
      <button className={btn(false)} onClick={() => mutate((it) => it.slice(0, -1))}>
        ↩ Последняя
      </button>
      <button className={btn(false)} onClick={() => mutate(() => [])}>
        ✕ Очистить
      </button>
    </div>
  );
}

export function ChartControlsBar({
  toggles,
  onChange,
}: {
  toggles: ChartToggles;
  onChange: (t: ChartToggles) => void;
}) {
  const items: { key: keyof ChartToggles; label: string }[] = useMemo(
    () => [
      { key: "bb", label: "Bollinger" },
      { key: "vwap", label: "VWAP" },
      { key: "ichimoku", label: "Ichimoku" },
      { key: "levels", label: "Уровни" },
      { key: "fib", label: "Фибоначчи" },
      { key: "rsi", label: "RSI" },
      { key: "macd", label: "MACD" },
      { key: "stoch", label: "Stoch" },
    ],
    []
  );
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((it) => (
        <button
          key={it.key}
          onClick={() => onChange({ ...toggles, [it.key]: !toggles[it.key] })}
          className={`rounded-lg px-2 py-0.5 text-[11px] transition-colors ${
            toggles[it.key]
              ? "bg-[#0a84ff]/10 font-medium text-[#0a84ff]"
              : "bg-black/[0.04] text-muted-foreground hover:bg-black/[0.08]"
          }`}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

/** Standalone equity-curve mini chart (journal, backtest). */
export function EquityChart({ curve, height = 180 }: { curve: { time: number; value: number }[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!curve.length) {
      setEmpty(true);
      return;
    }
    setEmpty(false);
    const chart = createChart(el, { ...baseOptions, height });
    const dedup = curve.filter((p, i) => i === 0 || p.time > curve[i - 1].time);
    chart
      .addSeries(LineSeries, { color: "#0a84ff", lineWidth: 2, priceLineVisible: false })
      .setData(dedup.map((p) => ({ time: toLocalTime(p.time) as UTCTimestamp, value: p.value })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [curve, height]);

  if (empty) {
    return (
      <div className="flex items-center justify-center text-xs text-muted-foreground" style={{ height }}>
        Пока нет закрытых сделок
      </div>
    );
  }
  return <div ref={ref} style={{ height }} className="w-full" />;
}
