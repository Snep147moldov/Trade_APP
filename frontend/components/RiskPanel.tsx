"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { api, fmtMoney2, pretty, type RiskMonitor } from "@/lib/api";

const SEV_STYLE: Record<string, string> = {
  critical: "border-[#ff3b30]/30 bg-[#ff3b30]/5",
  warning: "border-amber-300/50 bg-amber-50",
  info: "border-black/5 bg-black/[0.02]",
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
      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
          Загружаю риск-монитор…
        </CardContent>
      </Card>
    );
  }

  const l = data.limits;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-5 gap-3">
        <Metric label="Дневной P&L" value={fmtMoney2(l.daily_pnl)} tone={l.daily_pnl >= 0 ? "up" : "down"} />
        <Metric label="Плавающий P&L" value={fmtMoney2(data.floating_eur)} tone={data.floating_eur >= 0 ? "up" : "down"} />
        <Metric label="Открытый риск" value={`${l.open_risk_pct.toFixed(1)}%`} sub={fmtMoney2(l.open_risk)} />
        <Metric label="Просадка" value={`${l.drawdown_pct.toFixed(1)}%`} />
        <Metric label="Торговля" value={l.can_trade ? "Разрешена" : "Остановлена"} tone={l.can_trade ? "up" : "down"} />
      </div>

      {data.alerts.length > 0 && (
        <div className="space-y-2">
          {data.alerts.map((a, i) => (
            <div key={i} className={`rounded-2xl border p-3 ${SEV_STYLE[a.severity]}`}>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className={`rounded-full text-[9px] ${
                  a.severity === "critical" ? "bg-[#ff3b30]/10 text-[#ff3b30]" :
                  a.severity === "warning" ? "bg-amber-100 text-amber-800" : ""}`}>
                  {a.severity === "critical" ? "критично" : a.severity === "warning" ? "внимание" : "инфо"}
                </Badge>
                <p className="text-xs font-semibold">{a.title}</p>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">{a.detail}</p>
              <p className="mt-1 text-[11px] font-medium text-[#0a84ff]">→ {a.action}</p>
            </div>
          ))}
        </div>
      )}
      {data.alerts.length === 0 && (
        <p className="rounded-2xl bg-[#34c759]/5 p-3 text-xs text-[#34c759]">
          ✓ Риск-профиль в норме: лимиты не нарушены, экспозиция под контролем.
        </p>
      )}

      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="pt-4">
          <h3 className="mb-2 text-sm font-semibold tracking-tight">
            Открытые позиции ({data.positions.length})
          </h3>
          {data.positions.length === 0 ? (
            <p className="py-4 text-center text-xs text-muted-foreground">Нет открытых сигналов.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Инструмент</TableHead>
                  <TableHead>Напр.</TableHead>
                  <TableHead className="text-right">Вход</TableHead>
                  <TableHead className="text-right">Цена</TableHead>
                  <TableHead className="text-right">SL (тек.)</TableHead>
                  <TableHead className="text-right">R сейчас</TableHead>
                  <TableHead className="text-right">Плав. P&L</TableHead>
                  <TableHead>Управление</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.positions.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="text-xs font-medium">{pretty(p.instrument)} · {p.timeframe}</TableCell>
                    <TableCell className={`text-xs font-semibold ${p.direction === "BUY" ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                      {p.direction === "BUY" ? "LONG" : "SHORT"}
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{p.entry}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{p.price ?? "—"}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{p.stop_loss}</TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${
                      (p.r_now ?? 0) >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                      {p.r_now != null ? `${p.r_now > 0 ? "+" : ""}${p.r_now.toFixed(2)}R` : "—"}
                    </TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${
                      (p.floating_eur ?? 0) >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                      {p.floating_eur != null ? fmtMoney2(p.floating_eur) : "—"}
                    </TableCell>
                    <TableCell className="text-[10px] text-muted-foreground">
                      {[p.be_moved && "безубыток", p.partial_taken && "частичная фиксация"]
                        .filter(Boolean).join(" · ") || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
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
