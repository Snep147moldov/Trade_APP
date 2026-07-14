"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, pretty, type HeatmapResult } from "@/lib/api";

function heatColor(chg: number): string {
  const capped = Math.max(-2, Math.min(2, chg));
  const t = Math.abs(capped) / 2; // 0..1
  const alpha = 0.12 + t * 0.75;
  return capped >= 0
    ? `rgba(52, 199, 89, ${alpha})`
    : `rgba(255, 59, 48, ${alpha})`;
}

export function HeatmapPanel({ onPick }: { onPick: (symbol: string) => void }) {
  const [data, setData] = useState<HeatmapResult | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.heatmap());
    } catch {
      /* ignore */
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!data) {
    return (
      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
          {loading ? "Строю тепловую карту (первый раз ~30 с)…" : "Нет данных"}
        </CardContent>
      </Card>
    );
  }

  const strength = Object.entries(data.currency_strength);

  return (
    <div className="space-y-6">
      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="pt-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold tracking-tight">Сила валют G8 (24ч)</h3>
            <Button size="sm" variant="outline" className="rounded-xl" onClick={load} disabled={loading}>
              {loading ? "Обновляю…" : "Обновить"}
            </Button>
          </div>
          <div className="grid grid-cols-8 gap-2">
            {strength.map(([ccy, v]) => (
              <div key={ccy} className="rounded-xl p-3 text-center"
                   style={{ background: heatColor(v * 4) }}>
                <p className="text-sm font-bold">{ccy}</p>
                <p className="text-xs tabular-nums">{v > 0 ? "+" : ""}{v.toFixed(2)}%</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {data.categories.map((cat) => (
        cat.items.length > 0 && (
          <Card key={cat.key} className="rounded-2xl border-black/5 shadow-sm">
            <CardContent className="pt-4">
              <h3 className="mb-2 text-sm font-semibold tracking-tight">{cat.label}</h3>
              <div className="grid grid-cols-8 gap-1.5">
                {cat.items.map((it) => (
                  <button key={it.symbol} onClick={() => onPick(it.symbol)}
                          title={`${it.name} · ATR ${it.atr_pct}% · RSI ${it.rsi14 ?? "—"}`}
                          className="rounded-lg p-2 text-left transition-transform hover:scale-[1.03]"
                          style={{ background: heatColor(it.chg_pct) }}>
                    <p className="truncate text-[10px] font-semibold">{pretty(it.symbol)}</p>
                    <p className="text-[10px] tabular-nums">
                      {it.chg_pct > 0 ? "+" : ""}{it.chg_pct}%
                    </p>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        )
      ))}
    </div>
  );
}
