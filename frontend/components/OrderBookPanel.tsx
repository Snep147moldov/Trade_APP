"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, fmtMoney2, pretty, type DepthResult } from "@/lib/api";

export function OrderBookPanel({ instrument, tf }: {
  instrument: string | null;
  tf: string;
}) {
  const [data, setData] = useState<DepthResult | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!instrument) return;
    setLoading(true);
    try {
      setData(await api.depth(instrument, tf));
    } catch {
      setData(null);
    }
    setLoading(false);
  }, [instrument, tf]);

  useEffect(() => {
    load();
    const id = setInterval(load, 20_000);
    return () => clearInterval(id);
  }, [load]);

  if (!instrument) {
    return (
      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
          Выберите инструмент слева.
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
          {loading ? "Загружаю глубину рынка…" : "Нет данных."}
        </CardContent>
      </Card>
    );
  }

  const maxBook = Math.max(
    ...data.book.bids.map((b) => b.size),
    ...data.book.asks.map((a) => a.size), 1);
  const maxProfile = Math.max(...data.volume_profile.map((p) => p.volume), 1);
  const profileDesc = [...data.volume_profile].reverse();

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-3">
        <Metric label="Средняя цена" value={String(data.mid)} />
        <Metric label="Оценка спреда" value={`${data.spread.pips} п.`}
                sub={`раунд-трип 1 лот ≈ ${fmtMoney2(data.spread.lot_cost_eur)}`} />
        <Metric label="Дисбаланс книги" value={`${data.imbalance > 0 ? "+" : ""}${(data.imbalance * 100).toFixed(0)}%`}
                sub={data.imbalance > 0.1 ? "перевес покупателей" : data.imbalance < -0.1 ? "перевес продавцов" : "сбалансировано"}
                tone={data.imbalance > 0.1 ? "up" : data.imbalance < -0.1 ? "down" : undefined} />
        <Metric label="Спред / ATR" value={data.spread.atr_ratio_pct != null ? `${data.spread.atr_ratio_pct}%` : "—"}
                sub="доля волатильности, съедаемая спредом" />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <Card className="rounded-2xl border-black/5 shadow-sm">
          <CardContent className="pt-4">
            <div className="mb-2 flex items-center gap-2">
              <h3 className="text-sm font-semibold tracking-tight">
                Стакан · {pretty(data.instrument)}
              </h3>
              {data.synthetic && (
                <Badge variant="secondary" className="rounded-full bg-amber-100 text-[9px] text-amber-800">
                  оценка ликвидности
                </Badge>
              )}
              <Button size="sm" variant="ghost" className="ml-auto h-6 rounded-lg text-[10px]"
                      onClick={load} disabled={loading}>
                обновить
              </Button>
            </div>
            <div className="space-y-0.5">
              {[...data.book.asks].reverse().map((a, i) => (
                <Row key={`a${i}`} price={a.price} size={a.size} max={maxBook} side="ask" />
              ))}
              <div className="my-1 rounded-lg bg-black/[0.04] px-2 py-1 text-center text-xs font-semibold tabular-nums">
                {data.mid}
              </div>
              {data.book.bids.map((b, i) => (
                <Row key={`b${i}`} price={b.price} size={b.size} max={maxBook} side="bid" />
              ))}
            </div>
            <p className="mt-2 text-[10px] leading-snug text-muted-foreground">
              Провайдер не отдаёт реальный L2 для форекса — стакан построен из
              волатильности, профиля объёма и зон S/R (детерминированная оценка).
            </p>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-black/5 shadow-sm">
          <CardContent className="pt-4">
            <h3 className="mb-2 text-sm font-semibold tracking-tight">
              Профиль объёма (реальные данные, {data.timeframe})
            </h3>
            <div className="space-y-0.5">
              {profileDesc.map((p, i) => {
                const isLarge = data.large_levels.some((l) => l.price === p.price);
                return (
                  <div key={i} className="flex items-center gap-2">
                    <span className={`w-[76px] shrink-0 text-right text-[10px] tabular-nums ${
                      isLarge ? "font-bold" : "text-muted-foreground"}`}>
                      {p.price}
                    </span>
                    <div className="h-3 flex-1 overflow-hidden rounded-sm bg-black/[0.03]">
                      <div className="flex h-full" style={{ width: `${(p.volume / maxProfile) * 100}%` }}>
                        <div className="h-full bg-[#34c759]/60" style={{ width: `${p.buy_frac * 100}%` }} />
                        <div className="h-full flex-1 bg-[#ff3b30]/50" />
                      </div>
                    </div>
                    {isLarge && <span className="text-[9px] text-[#ff9f0a]">◆ крупный</span>}
                  </div>
                );
              })}
            </div>
            <p className="mt-2 text-[10px] text-muted-foreground">
              Зелёная доля — объём в растущих барах. ◆ — три крупнейших уровня
              (вероятные зоны интереса / «крупные заявки»).
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Row({ price, size, max, side }: {
  price: number; size: number; max: number; side: "bid" | "ask";
}) {
  const w = Math.max(3, (size / max) * 100);
  return (
    <div className="relative flex h-[18px] items-center justify-between px-2 text-[10px] tabular-nums">
      <div className={`absolute inset-y-0 ${side === "bid" ? "left-0 bg-[#34c759]/12" : "right-0 bg-[#ff3b30]/12"} rounded-sm`}
           style={{ width: `${w}%` }} />
      <span className={`relative z-[1] ${side === "bid" ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
        {price}
      </span>
      <span className="relative z-[1] text-muted-foreground">{size.toFixed(1)}</span>
    </div>
  );
}

function Metric({ label, value, sub, tone }: {
  label: string; value: string; sub?: string; tone?: "up" | "down";
}) {
  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardContent className="pt-4">
        <p className="text-[10px] text-muted-foreground">{label}</p>
        <p className={`text-lg font-semibold tabular-nums tracking-tight ${
          tone === "up" ? "text-[#34c759]" : tone === "down" ? "text-[#ff3b30]" : ""}`}>
          {value}
        </p>
        {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}
