"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, fmtPct, pretty, type ScreenerRow } from "@/lib/api";

const CATS = [
  { key: "watchlist", label: "Избранное" },
  { key: "forex", label: "Форекс" },
  { key: "metals", label: "Металлы" },
  { key: "indices", label: "Индексы" },
  { key: "energy", label: "Энергия" },
  { key: "stocks", label: "Акции" },
  { key: "etf", label: "ETF" },
  { key: "crypto", label: "Крипто" },
];

type SortKey = "momentum_score" | "chg_24h_pct" | "atr_pct" | "rsi14" | "volume_ratio" | "adx14";

export function ScreenerPanel({ onPick }: { onPick: (symbol: string) => void }) {
  const [category, setCategory] = useState("forex");
  const [rows, setRows] = useState<ScreenerRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("momentum_score");
  const [onlyBreakouts, setOnlyBreakouts] = useState(false);
  const [onlyTrending, setOnlyTrending] = useState(false);

  const load = useCallback(async (cat: string, force = false) => {
    setLoading(true);
    try {
      setRows((await api.screener(cat, force)).rows);
    } catch {
      setRows([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load(category);
  }, [category, load]);

  let view = [...rows];
  if (onlyBreakouts) view = view.filter((r) => r.breakout !== 0);
  if (onlyTrending) view = view.filter((r) => (r.adx14 ?? 0) >= 20);
  view.sort((a, b) => Math.abs((b[sortKey] as number) ?? 0) - Math.abs((a[sortKey] as number) ?? 0));

  const th = (k: SortKey, label: string) => (
    <TableHead className="cursor-pointer select-none text-right"
               onClick={() => setSortKey(k)}>
      {label}{sortKey === k ? " ↓" : ""}
    </TableHead>
  );

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardContent className="pt-4">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <h3 className="text-sm font-semibold tracking-tight">Скринер рынка</h3>
          <Tabs value={category} onValueChange={setCategory}>
            <TabsList className="h-8 rounded-xl">
              {CATS.map((c) => (
                <TabsTrigger key={c.key} value={c.key} className="rounded-lg px-2.5 text-xs">
                  {c.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <div className="ml-auto flex items-center gap-2">
            <FilterChip active={onlyBreakouts} onClick={() => setOnlyBreakouts((v) => !v)}>
              Пробои
            </FilterChip>
            <FilterChip active={onlyTrending} onClick={() => setOnlyTrending((v) => !v)}>
              Тренд (ADX≥20)
            </FilterChip>
            <Button size="sm" variant="outline" className="rounded-xl"
                    onClick={() => load(category, true)} disabled={loading}>
              {loading ? "Сканирую…" : "Обновить"}
            </Button>
          </div>
        </div>

        {view.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            {loading ? "Сканирую рынок…" : "Нет данных — попробуйте другую категорию."}
          </p>
        ) : (
          <div className="max-h-[520px] overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Инструмент</TableHead>
                  <TableHead className="text-right">Цена</TableHead>
                  {th("chg_24h_pct", "24ч %")}
                  {th("atr_pct", "ATR %")}
                  {th("rsi14", "RSI")}
                  {th("adx14", "ADX")}
                  {th("volume_ratio", "Объём ×")}
                  {th("momentum_score", "Моментум")}
                  <TableHead>Сигналы</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {view.slice(0, 60).map((r) => (
                  <TableRow key={r.symbol} className="cursor-pointer"
                            onClick={() => onPick(r.symbol)}>
                    <TableCell className="text-xs font-medium">
                      {pretty(r.symbol)}
                      <span className="ml-1 text-[10px] text-muted-foreground">{r.name}</span>
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{r.price}</TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${
                      r.chg_24h_pct >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                      {fmtPct(r.chg_24h_pct, 2)}
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{r.atr_pct}%</TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${
                      (r.rsi14 ?? 50) >= 70 ? "text-[#ff3b30]" : (r.rsi14 ?? 50) <= 30 ? "text-[#34c759]" : ""}`}>
                      {r.rsi14 ?? "—"}
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{r.adx14 ?? "—"}</TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${
                      r.volume_ratio >= 2 ? "font-semibold text-[#ff9f0a]" : ""}`}>
                      {r.volume_ratio}
                    </TableCell>
                    <TableCell className={`text-right text-xs font-semibold tabular-nums ${
                      r.momentum_score >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                      {r.momentum_score > 0 ? "+" : ""}{r.momentum_score}
                    </TableCell>
                    <TableCell className="text-[10px]">
                      {r.breakout === 1 && <span className="mr-1 rounded bg-[#34c759]/10 px-1 py-0.5 text-[#34c759]">пробой ↑</span>}
                      {r.breakout === -1 && <span className="mr-1 rounded bg-[#ff3b30]/10 px-1 py-0.5 text-[#ff3b30]">пробой ↓</span>}
                      {r.trend === 1 && <span className="text-[#34c759]">↑ тренд</span>}
                      {r.trend === -1 && <span className="text-[#ff3b30]">↓ тренд</span>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        <p className="mt-2 text-[10px] text-muted-foreground">
          Клик по строке — открыть инструмент. Массовое сканирование использует
          свободный лимит API и кэш (10 мин); графики и сигналы всегда в приоритете.
        </p>
      </CardContent>
    </Card>
  );
}

function FilterChip({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button onClick={onClick}
            className={`rounded-lg px-2 py-1 text-[11px] transition-colors ${
              active ? "bg-[#0a84ff]/10 font-medium text-[#0a84ff]"
                     : "bg-black/[0.04] text-muted-foreground hover:bg-black/[0.08]"}`}>
      {children}
    </button>
  );
}
