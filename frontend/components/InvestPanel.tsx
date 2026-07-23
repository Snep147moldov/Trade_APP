"use client";

import { useEffect, useRef, useState } from "react";
import {
  AreaSeries,
  ColorType,
  UTCTimestamp,
  createChart,
} from "lightweight-charts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { SignalStats } from "@/lib/api";
import { fmtMoney, fmtMoney2, toLocalTime } from "@/lib/api";

function Stat({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  return (
    <div className="rounded-xl bg-muted/50 p-3">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p
        className={`text-base font-semibold tabular-nums tracking-tight ${
          tone === "up" ? "text-[#34c759]" : tone === "down" ? "text-[#ff3b30]" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}

export function InvestPanel({
  stats,
  equity,
  onEquityChange,
}: {
  stats: SignalStats | null;
  equity: number;
  onEquityChange: (v: number) => Promise<void>;
}) {
  const chartRef = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState(String(equity));
  const [saving, setSaving] = useState(false);

  useEffect(() => setDraft(String(equity)), [equity]);

  useEffect(() => {
    const el = chartRef.current;
    if (!el || !stats || stats.equity_curve.length === 0) return;
    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8e8e93",
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: "rgba(0,0,0,0.04)" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
      height: 160,
      autoSize: true,
    });
    const up = (stats.total_money ?? 0) >= 0;
    const series = chart.addSeries(AreaSeries, {
      lineColor: up ? "#34c759" : "#ff3b30",
      topColor: up ? "rgba(52,199,89,0.25)" : "rgba(255,59,48,0.25)",
      bottomColor: "rgba(0,0,0,0)",
      lineWidth: 2,
      priceLineVisible: false,
    });
    series.setData(
      stats.equity_curve.map((p) => ({
        time: toLocalTime(p.time) as UTCTimestamp,
        value: p.value,
      }))
    );
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [stats]);

  const save = async () => {
    const v = parseFloat(draft);
    if (Number.isNaN(v) || v <= 0) return;
    setSaving(true);
    await onEquityChange(v);
    setSaving(false);
  };

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold tracking-tight">
          Инвестиции и доходность
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Если следовать рекомендациям: реализованный результат + открытый риск
        </p>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex items-end gap-2">
          <div className="flex-1">
            <p className="mb-1 text-[11px] text-muted-foreground">Инвестируемая сумма, €</p>
            <Input
              type="number"
              step="100"
              className="rounded-xl"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          </div>
          <Button variant="outline" className="rounded-xl" onClick={save} disabled={saving}>
            {saving ? "…" : "Применить"}
          </Button>
        </div>

        {stats && (
          <div className="mb-3 grid grid-cols-2 gap-2">
            <Stat label="Текущий капитал" value={fmtMoney(stats.current_equity)} />
            <Stat
              label="Итог по закрытым"
              value={`${stats.total_money >= 0 ? "+" : ""}${fmtMoney2(stats.total_money)} (${stats.return_pct >= 0 ? "+" : ""}${stats.return_pct}%)`}
              tone={stats.total_money > 0 ? "up" : stats.total_money < 0 ? "down" : undefined}
            />
            <Stat
              label={`Сегодня${stats.today_closed ? ` · ${stats.today_wins}П/${stats.today_closed - stats.today_wins}У` : ""}`}
              value={stats.today_closed
                ? `${stats.today_money >= 0 ? "+" : ""}${fmtMoney2(stats.today_money)}`
                : "нет закрытых"}
              tone={stats.today_money > 0 ? "up" : stats.today_money < 0 ? "down" : undefined}
            />
            <Stat
              label={`За 7 дней · ${stats.week_closed} сдел.`}
              value={stats.week_closed
                ? `${stats.week_money >= 0 ? "+" : ""}${fmtMoney2(stats.week_money)}`
                : "—"}
              tone={stats.week_money > 0 ? "up" : stats.week_money < 0 ? "down" : undefined}
            />
            <Stat label="Риск по открытым" value={`−${fmtMoney2(stats.open_risk)}`} tone="down" />
            <Stat
              label="Потенциал по открытым"
              value={`+${fmtMoney2(stats.open_potential)}`}
              tone="up"
            />
          </div>
        )}

        {stats?.mt5?.connected && (
          <div className="mb-3 rounded-xl border border-[#0a84ff]/20 bg-[#0a84ff]/[0.04] p-3">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[#0a84ff]">
              Реально в MT5 · брокер
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Stat
                label="Баланс · эквити"
                value={`${fmtMoney2(stats.mt5.balance ?? 0)} · ${fmtMoney2(stats.mt5.equity ?? 0)}`}
              />
              <Stat
                label={`Плавающий · ${stats.mt5.open_positions} поз.`}
                value={stats.mt5.floating == null
                  ? "—"
                  : `${stats.mt5.floating >= 0 ? "+" : ""}${fmtMoney2(stats.mt5.floating)}`}
                tone={(stats.mt5.floating ?? 0) > 0 ? "up" : (stats.mt5.floating ?? 0) < 0 ? "down" : undefined}
              />
              <Stat
                label="Сегодня в MT5 (закрытые)"
                value={stats.mt5.today_real == null
                  ? "—"
                  : `${stats.mt5.today_real >= 0 ? "+" : ""}${fmtMoney2(stats.mt5.today_real)}`}
                tone={(stats.mt5.today_real ?? 0) > 0 ? "up" : (stats.mt5.today_real ?? 0) < 0 ? "down" : undefined}
              />
              <Stat
                label="За 7 дней в MT5"
                value={stats.mt5.week_real == null
                  ? "—"
                  : `${stats.mt5.week_real >= 0 ? "+" : ""}${fmtMoney2(stats.mt5.week_real)}`}
                tone={(stats.mt5.week_real ?? 0) > 0 ? "up" : (stats.mt5.week_real ?? 0) < 0 ? "down" : undefined}
              />
            </div>
            <p className="mt-1.5 text-[10px] text-muted-foreground">
              Данные брокера (Fusion Markets), обновляются раз в минуту —
              включая ордера ×2/×3 из Telegram.
            </p>
          </div>
        )}

        {stats && stats.equity_curve.length > 0 ? (
          <>
            <p className="mb-1 text-[11px] text-muted-foreground">Кривая капитала</p>
            <div ref={chartRef} className="h-[160px] w-full" />
          </>
        ) : (
          <p className="rounded-xl bg-muted/50 p-3 text-center text-xs text-muted-foreground">
            Кривая капитала появится после первых закрытых сигналов.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
