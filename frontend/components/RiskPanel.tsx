"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  CircleCheck,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";

import { api, fmtMoney2, pretty, type RiskMonitor } from "@/lib/api";

/** Цвет корешка по важности: на стеклянной поверхности рамка почти не видна,
 *  а вертикальная полоса слева читается сразу. */
const SEV: Record<string, { bar: string; ring: string; text: string; label: string }> = {
  critical: { bar: "bg-neg", ring: "ring-neg/30", text: "text-neg", label: "критично" },
  warning: { bar: "bg-warn", ring: "ring-warn/30", text: "text-warn", label: "внимание" },
  info: { bar: "bg-brand", ring: "ring-brand/25", text: "text-brand-ink", label: "инфо" },
};

export function RiskPanel() {
  const [data, setData] = useState<RiskMonitor | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await api.riskMonitor());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 20_000);
    return () => clearInterval(id);
  }, [refresh]);

  if (!data) {
    return (
      <div className="glass flex h-full items-center justify-center rounded-3xl text-sm text-muted-foreground">
        Загружаю риск-монитор…
      </div>
    );
  }

  const l = data.limits;

  return (
    <div className="flex flex-col gap-3 lg:h-full lg:min-h-0">
      <div className="grid shrink-0 grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Tile label="Дневной P&L" value={fmtMoney2(l.daily_pnl)} tone={l.daily_pnl >= 0 ? "pos" : "neg"} />
        <Tile
          label="Плавающий P&L"
          value={fmtMoney2(data.floating_eur)}
          tone={data.floating_eur >= 0 ? "pos" : "neg"}
        />
        <Tile label="Открытый риск" value={`${l.open_risk_pct.toFixed(1)}%`} hint={fmtMoney2(l.open_risk)} />
        <Tile label="Просадка" value={`${l.drawdown_pct.toFixed(1)}%`} tone={l.drawdown_pct > 0 ? "warn" : undefined} />
        <Tile
          label="Торговля"
          value={l.can_trade ? "Разрешена" : "Остановлена"}
          tone={l.can_trade ? "pos" : "neg"}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 xl:min-h-0 xl:flex-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        {/* ------------------------------------------------ предупреждения */}
        <section className="glass flex max-h-[55dvh] flex-col rounded-3xl xl:max-h-none xl:min-h-0">
          <h3 className="shrink-0 px-4 pb-2 pt-3.5 text-sm font-semibold tracking-tight">
            Предупреждения
            {data.alerts.length > 0 && (
              <span className="ml-2 rounded-full bg-foreground/10 px-1.5 py-0.5 text-xs sm:text-[10px] font-medium tabular-nums text-muted-foreground">
                {data.alerts.length}
              </span>
            )}
          </h3>
          <div className="scrollbar-thin min-h-0 flex-1 space-y-2 overflow-y-auto px-3 pb-3">
            {data.alerts.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-2 py-8 text-center">
                <CircleCheck className="h-8 w-8 text-pos" />
                <p className="text-xs text-muted-foreground">
                  Лимиты не нарушены, экспозиция под контролем
                </p>
              </div>
            ) : (
              data.alerts.map((a, i) => {
                const s = SEV[a.severity] ?? SEV.info;
                return (
                  <div
                    key={i}
                    style={{ animationDelay: `${i * 40}ms` }}
                    className={`glass rise relative overflow-hidden rounded-2xl p-3 pl-4 ring-1 ${s.ring}`}
                  >
                    <span className={`absolute inset-y-0 left-0 w-1 ${s.bar}`} />
                    <div className="flex items-center gap-2">
                      <TriangleAlert className={`h-3.5 w-3.5 shrink-0 ${s.text}`} />
                      <p className="min-w-0 flex-1 truncate text-[15px] sm:text-[13px] font-semibold">{a.title}</p>
                      <span className={`shrink-0 text-xs sm:text-[10px] ${s.text}`}>{s.label}</span>
                    </div>
                    <p className="mt-1 text-[13px] sm:text-[11px] leading-relaxed text-muted-foreground">
                      {a.detail}
                    </p>
                    <p className="mt-1.5 text-[13px] sm:text-[11px] font-medium text-brand-ink">→ {a.action}</p>
                  </div>
                );
              })
            )}
          </div>
        </section>

        {/* -------------------------------------------- открытые позиции */}
        <section className="glass flex max-h-[55dvh] flex-col rounded-3xl xl:max-h-none xl:min-h-0">
          <h3 className="shrink-0 px-4 pb-2 pt-3.5 text-sm font-semibold tracking-tight">
            Открытые позиции
            {data.positions.length > 0 && (
              <span className="ml-2 rounded-full bg-foreground/10 px-1.5 py-0.5 text-xs sm:text-[10px] font-medium tabular-nums text-muted-foreground">
                {data.positions.length}
              </span>
            )}
          </h3>
          <div className="scrollbar-thin min-h-0 flex-1 space-y-1 overflow-y-auto px-2 pb-3">
            {data.positions.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-2 py-8 text-center">
                <ShieldAlert className="h-8 w-8 text-muted-foreground/50" />
                <p className="text-xs text-muted-foreground">Нет открытых сигналов</p>
              </div>
            ) : (
              data.positions.map((p, i) => {
                const long = p.direction === "BUY";
                const good = (p.r_now ?? 0) >= 0;
                const marks = [p.be_moved && "безубыток", p.partial_taken && "частичная фиксация"]
                  .filter(Boolean)
                  .join(" · ");
                return (
                  <div
                    key={p.id}
                    style={{ animationDelay: `${i * 30}ms` }}
                    className="rise rounded-2xl px-2 py-2 transition-colors hover:bg-accent/60"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                          long ? "bg-pos/12 text-pos" : "bg-neg/12 text-neg"
                        }`}
                      >
                        {long ? (
                          <ArrowUpRight className="h-4 w-4" />
                        ) : (
                          <ArrowDownLeft className="h-4 w-4" />
                        )}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[15px] sm:text-[13px] font-medium">
                          {pretty(p.instrument)}
                          <span className="ml-1.5 font-normal text-muted-foreground">
                            {p.timeframe}
                          </span>
                        </p>
                        <p className="truncate text-[13px] sm:text-[11px] tabular-nums text-muted-foreground">
                          вход {p.entry} · сейчас {p.price ?? "—"} · стоп {p.stop_loss}
                          {marks && ` · ${marks}`}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p
                          className={`text-[15px] sm:text-[13px] font-medium tabular-nums ${
                            good ? "text-pos" : "text-neg"
                          }`}
                        >
                          {p.floating_eur != null ? fmtMoney2(p.floating_eur) : "—"}
                        </p>
                        <p
                          className={`text-[13px] sm:text-[11px] tabular-nums ${
                            good ? "text-pos/80" : "text-neg/80"
                          }`}
                        >
                          {p.r_now != null
                            ? `${p.r_now > 0 ? "+" : ""}${p.r_now.toFixed(2)}R`
                            : "—"}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function Tile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "pos" | "neg" | "warn";
}) {
  const color =
    tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : tone === "warn" ? "text-warn" : "";
  return (
    <div className="glass rise rounded-2xl p-3 sm:p-4">
      <p className="truncate text-[13px] sm:text-[11px] text-muted-foreground">{label}</p>
      <p className={`mt-0.5 text-lg font-semibold tracking-tight tabular-nums sm:text-xl ${color}`}>
        {value}
      </p>
      {hint && <p className="mt-0.5 truncate text-[13px] sm:text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}
