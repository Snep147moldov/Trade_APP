"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  LineSeries,
  UTCTimestamp,
  createChart,
} from "lightweight-charts";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, pretty, toLocalTime, type Analysis } from "@/lib/api";
import { chartBase, chartPalette } from "@/lib/chart-theme";
import { useIsDark } from "@/components/ThemeToggle";

const TFS = ["1m", "5m", "15m", "40m", "1h", "4h", "1d"];

interface Slot {
  instrument: string;
  tf: string;
}

const SLOTS_KEY = "cnx_multichart";

function loadSlots(fallback: string[]): Slot[] {
  if (typeof window !== "undefined") {
    try {
      const saved = JSON.parse(localStorage.getItem(SLOTS_KEY) ?? "null");
      if (Array.isArray(saved) && saved.length === 4) return saved;
    } catch { /* ignore */ }
  }
  return [0, 1, 2, 3].map((i) => ({
    instrument: fallback[i % Math.max(fallback.length, 1)] ?? "EUR_USD",
    tf: ["15m", "1h", "4h", "1d"][i],
  }));
}

function MiniChart({ analysis }: { analysis: Analysis | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const dark = useIsDark();

  useEffect(() => {
    const el = ref.current;
    if (!el || !analysis) return;
    const C = chartPalette();
    const chart = createChart(el, { ...chartBase(), height: 260 });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: C.up, downColor: C.down, wickUpColor: C.up, wickDownColor: C.down,
      borderVisible: false,
    });
    candles.setData(analysis.candles.map((c) => ({
      time: toLocalTime(c.time) as UTCTimestamp,
      open: c.open, high: c.high, low: c.low, close: c.close,
    })));
    const line = (values: (number | null)[], color: string) =>
      chart.addSeries(LineSeries, {
        color, lineWidth: 1, priceLineVisible: false,
        lastValueVisible: false, crosshairMarkerVisible: false,
      }).setData(
        analysis.candles
          .map((c, i) => ({ time: toLocalTime(c.time) as UTCTimestamp, value: values[i] }))
          .filter((p): p is { time: UTCTimestamp; value: number } => p.value != null));
    line(analysis.overlays.ema20, C.brand);
    line(analysis.overlays.ema50, C.warn);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [analysis, dark]);

  return <div ref={ref} className="h-[260px] w-full" />;
}

function ChartSlot({ slot, onChange }: { slot: Slot; onChange: (s: Slot) => void }) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [symbolDraft, setSymbolDraft] = useState(slot.instrument);
  const [err, setErr] = useState(false);

  const load = useCallback(async () => {
    try {
      setAnalysis(await api.analysis(slot.instrument, slot.tf));
      setErr(false);
    } catch {
      setErr(true);
    }
  }, [slot.instrument, slot.tf]);

  useEffect(() => {
    setAnalysis(null);
    load();
    const id = setInterval(load, 45_000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => setSymbolDraft(slot.instrument), [slot.instrument]);

  const dirColor = analysis?.direction === "BUY" ? "text-pos"
    : analysis?.direction === "SELL" ? "text-neg" : "text-muted-foreground";

  return (
    <Card className="rounded-2xl border-border shadow-sm">
      <CardContent className="pt-3">
        <div className="mb-1.5 flex items-center gap-2">
          <form onSubmit={(e) => {
            e.preventDefault();
            onChange({ ...slot, instrument: symbolDraft.toUpperCase().replace("/", "_").trim() });
          }}>
            <Input className="h-7 w-[110px] rounded-lg text-xs font-semibold" value={symbolDraft}
                   onChange={(e) => setSymbolDraft(e.target.value)} />
          </form>
          <select className="h-7 rounded-lg border bg-transparent px-1 text-xs"
                  value={slot.tf} onChange={(e) => onChange({ ...slot, tf: e.target.value })}>
            {TFS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          {analysis && (
            <span className="ml-auto text-xs tabular-nums">
              {analysis.indicators.close}{" "}
              <span className={`font-semibold ${dirColor}`}>
                {analysis.direction} {analysis.score > 0 ? "+" : ""}{analysis.score.toFixed(2)}
              </span>
            </span>
          )}
        </div>
        {err ? (
          <div className="flex h-[260px] items-center justify-center text-xs text-muted-foreground">
            Неизвестный инструмент {pretty(slot.instrument)}
          </div>
        ) : analysis ? (
          <MiniChart analysis={analysis} />
        ) : (
          <div className="flex h-[260px] items-center justify-center text-xs text-muted-foreground">
            Загружаю {pretty(slot.instrument)} · {slot.tf}…
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function MultiChartGrid({ watchlist }: { watchlist: string[] }) {
  const [layout, setLayout] = useState<1 | 2 | 4>(4);
  const [slots, setSlots] = useState<Slot[]>(() => loadSlots(watchlist));

  const update = (i: number, s: Slot) => {
    setSlots((prev) => {
      const next = prev.map((old, j) => (j === i ? s : old));
      localStorage.setItem(SLOTS_KEY, JSON.stringify(next));
      return next;
    });
  };

  const visible = slots.slice(0, layout);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-1">
        <span className="mr-1 text-[13px] sm:text-[11px] text-muted-foreground">Раскладка:</span>
        {([1, 2, 4] as const).map((n) => (
          <button key={n} onClick={() => setLayout(n)}
                  className={`rounded-lg px-2.5 py-1 text-[13px] sm:text-[11px] transition-colors ${
                    layout === n ? "bg-brand/10 font-medium text-brand-ink"
                                 : "bg-muted text-muted-foreground hover:bg-accent"}`}>
            {n === 1 ? "1 график" : n === 2 ? "2 графика" : "сетка 2×2"}
          </button>
        ))}
        <span className="ml-2 text-xs sm:text-[10px] text-muted-foreground">
          Символ и таймфрейм каждого графика настраиваются независимо; раскладка сохраняется.
        </span>
      </div>
      <div className={`grid gap-4 ${layout === 1 ? "grid-cols-1" : "grid-cols-2"}`}>
        {visible.map((s, i) => (
          <ChartSlot key={i} slot={s} onChange={(ns) => update(i, ns)} />
        ))}
      </div>
    </div>
  );
}
