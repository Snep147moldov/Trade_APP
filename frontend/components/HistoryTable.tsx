"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SignalRow, SignalStats } from "@/lib/api";
import { api, fmtMoney2, pretty } from "@/lib/api";

const STATUS_STYLE: Record<string, string> = {
  open: "bg-[#0a84ff]/10 text-[#0a84ff]",
  hit_tp: "bg-[#34c759]/10 text-[#34c759]",
  hit_sl: "bg-[#ff3b30]/10 text-[#ff3b30]",
  expired: "bg-muted text-muted-foreground",
};

const STATUS_LABEL: Record<string, string> = {
  open: "Открыт",
  hit_tp: "Цель",
  hit_sl: "Стоп",
  expired: "Истёк",
};

const CLEAR_OPTIONS = [
  { value: "closed", label: "Все закрытые" },
  { value: "day1", label: "Старше 1 дня" },
  { value: "day7", label: "Старше 7 дней" },
  { value: "day30", label: "Старше 30 дней" },
  { value: "all", label: "Всю историю (включая открытые)" },
];

function dayKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function dayLabel(key: string): string {
  const today = dayKey(new Date().toISOString());
  const yesterday = dayKey(new Date(Date.now() - 86_400_000).toISOString());
  if (key === today) return "Сегодня";
  if (key === yesterday) return "Вчера";
  const [y, m, d] = key.split("-");
  return `${d}.${m}.${y}`;
}

function groupByDay(signals: SignalRow[]): { key: string; rows: SignalRow[] }[] {
  const groups: { key: string; rows: SignalRow[] }[] = [];
  for (const s of signals) {
    const key = dayKey(s.created_at);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.rows.push(s);
    else groups.push({ key, rows: [s] });
  }
  return groups;
}

export function HistoryTable({
  signals,
  stats,
  onEvaluate,
  evaluating,
  onChanged,
}: {
  signals: SignalRow[];
  stats: SignalStats | null;
  onEvaluate: () => void;
  evaluating: boolean;
  onChanged?: () => void;
}) {
  const [clearMode, setClearMode] = useState("closed");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const runClear = async () => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    setBusy(true);
    setMessage(null);
    try {
      const req =
        clearMode === "all"
          ? { scope: "all" as const }
          : clearMode === "closed"
            ? { scope: "closed" as const }
            : {
                scope: "closed" as const,
                older_than_days: parseInt(clearMode.replace("day", ""), 10),
              };
      const r = await api.clearSignals(req);
      setMessage(`Удалено: ${r.deleted}`);
      onChanged?.();
    } catch {
      setMessage("Не удалось удалить историю.");
    }
    setBusy(false);
  };

  const deleteOne = async (id: number) => {
    setDeletingId(id);
    try {
      await api.deleteSignal(id);
      onChanged?.();
    } catch {
      setMessage(`Не удалось удалить сигнал #${id}.`);
    }
    setDeletingId(null);
  };

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold tracking-tight">
            История сигналов
          </CardTitle>
          <div className="flex items-center gap-3">
            {stats && stats.closed > 0 && (
              <span className="text-xs text-muted-foreground">
                Прибыльных <b className="text-foreground">{stats.win_rate}%</b> ·{" "}
                {stats.wins}П / {stats.losses}У ·{" "}
                <b className={stats.total_money >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}>
                  {stats.total_money >= 0 ? "+" : ""}
                  {fmtMoney2(stats.total_money)}
                </b>
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              className="rounded-xl"
              onClick={onEvaluate}
              disabled={evaluating}
            >
              {evaluating ? "Проверяю…" : "Проверить результаты"}
            </Button>
          </div>
        </div>
        {signals.length > 0 && (
          <div className="flex items-center gap-2 pt-1">
            <select
              className="h-7 rounded-lg border bg-transparent px-2 text-xs"
              value={clearMode}
              onChange={(e) => {
                setClearMode(e.target.value);
                setConfirming(false);
              }}
            >
              {CLEAR_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <Button
              variant="outline"
              size="sm"
              className={`h-7 rounded-lg text-xs ${
                confirming ? "border-[#ff3b30]/50 text-[#ff3b30]" : "text-muted-foreground"
              }`}
              onClick={runClear}
              disabled={busy}
            >
              {busy ? "Удаляю…" : confirming ? "Точно удалить?" : "Очистить"}
            </Button>
            {confirming && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 rounded-lg text-xs text-muted-foreground"
                onClick={() => setConfirming(false)}
              >
                Отмена
              </Button>
            )}
            {message && <span className="text-xs text-muted-foreground">{message}</span>}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {signals.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Отслеживаемых сигналов пока нет. Создайте сигнал из карточки «Рекомендация».
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="text-xs">
                <TableHead>Пара</TableHead>
                <TableHead>ТФ</TableHead>
                <TableHead>Сторона</TableHead>
                <TableHead className="text-right">Вход</TableHead>
                <TableHead className="text-right">SL</TableHead>
                <TableHead className="text-right">TP</TableHead>
                <TableHead className="text-right">Оценка</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead className="text-right">Пункты</TableHead>
                <TableHead className="text-right">P&L, €</TableHead>
                <TableHead className="text-right">MT5, €</TableHead>
                <TableHead className="w-8" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {groupByDay(signals).map((g) => {
                const closed = g.rows.filter((s) => s.pnl_money != null);
                const dayMoney = closed.reduce((sum, s) => sum + (s.pnl_money ?? 0), 0);
                return [
                  <TableRow key={`day-${g.key}`} className="bg-muted/40 hover:bg-muted/40">
                    <TableCell colSpan={9} className="py-1.5 text-xs font-semibold">
                      {dayLabel(g.key)}
                      <span className="ml-2 font-normal text-muted-foreground">
                        {g.rows.length} сигн.
                      </span>
                    </TableCell>
                    <TableCell className="py-1.5 text-right text-xs font-semibold tabular-nums">
                      {closed.length > 0 && (
                        <span className={dayMoney >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}>
                          {dayMoney >= 0 ? "+" : ""}
                          {dayMoney.toFixed(2)}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="py-1.5 text-right text-xs font-semibold tabular-nums">
                      {(() => {
                        const mt5Rows = g.rows.filter((s) => s.mt5_pnl != null);
                        if (mt5Rows.length === 0) return null;
                        const m = mt5Rows.reduce((sum, s) => sum + (s.mt5_pnl ?? 0), 0);
                        return (
                          <span className={m >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}>
                            {m >= 0 ? "+" : ""}
                            {m.toFixed(2)}
                          </span>
                        );
                      })()}
                    </TableCell>
                    <TableCell className="py-1.5" />
                  </TableRow>,
                  ...g.rows.map((s) => (
                <TableRow key={s.id} className="group text-sm">
                  <TableCell className="font-medium">{pretty(s.instrument)}</TableCell>
                  <TableCell>{s.timeframe}</TableCell>
                  <TableCell>
                    <span
                      className={
                        s.direction === "BUY" ? "text-[#34c759]" : "text-[#ff3b30]"
                      }
                    >
                      {s.direction === "BUY" ? "Покупка" : "Продажа"}
                    </span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{s.entry}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.stop_loss}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.take_profit}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {s.score >= 0 ? "+" : ""}
                    {s.score.toFixed(2)}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="secondary"
                      className={`rounded-full text-[10px] ${STATUS_STYLE[s.status] ?? ""}`}
                    >
                      {STATUS_LABEL[s.status] ?? s.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {s.pnl_pips == null ? "—" : (
                      <span className={s.pnl_pips >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}>
                        {s.pnl_pips >= 0 ? "+" : ""}
                        {s.pnl_pips}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {s.pnl_money == null ? "—" : (
                      <span className={s.pnl_money >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}>
                        {s.pnl_money >= 0 ? "+" : ""}
                        {s.pnl_money.toFixed(2)}
                      </span>
                    )}
                  </TableCell>
                  <TableCell
                    className="text-right tabular-nums"
                    title={s.mt5_orders ? `${s.mt5_orders} орд. · ${s.mt5_volume} лот` : undefined}
                  >
                    {s.mt5_pnl == null ? (
                      s.mt5_orders ? (
                        <span className="text-[10px] text-[#0a84ff]">×{s.mt5_orders} откр.</span>
                      ) : "—"
                    ) : (
                      <span className={s.mt5_pnl >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}>
                        {s.mt5_pnl >= 0 ? "+" : ""}
                        {s.mt5_pnl.toFixed(2)}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <button
                      title={`Удалить сигнал #${s.id}`}
                      className="rounded-md px-1.5 py-0.5 text-xs text-muted-foreground opacity-0 transition-opacity hover:bg-[#ff3b30]/10 hover:text-[#ff3b30] group-hover:opacity-100 disabled:opacity-40"
                      disabled={deletingId === s.id}
                      onClick={() => deleteOne(s.id)}
                    >
                      ✕
                    </button>
                  </TableCell>
                </TableRow>
                  )),
                ];
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
