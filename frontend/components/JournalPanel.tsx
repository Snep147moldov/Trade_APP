"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { api, fmtMoney2, pretty, type JournalReview, type JournalStats, type SignalRow } from "@/lib/api";

export function JournalPanel({ signals, aiEnabled, onChanged }: {
  signals: SignalRow[];
  aiEnabled: boolean;
  onChanged: () => void;
}) {
  const [stats, setStats] = useState<JournalStats | null>(null);
  const [review, setReview] = useState<JournalReview | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [edit, setEdit] = useState<Record<number, { strategy: string; notes: string }>>({});

  const refresh = useCallback(async () => {
    try {
      setStats(await api.journalStats());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, signals.length]);

  const closed = signals.filter((s) => s.status !== "open");

  const save = async (id: number) => {
    const e = edit[id];
    if (!e) return;
    await api.patchSignal(id, { strategy: e.strategy, notes: e.notes }).catch(() => {});
    setEdit((m) => {
      const n = { ...m };
      delete n[id];
      return n;
    });
    onChanged();
    refresh();
  };

  const runReview = async () => {
    setReviewing(true);
    try {
      setReview(await api.journalReview());
    } catch (e) {
      setReview({
        summary: e instanceof Error && e.message.includes("400")
          ? "Нужен Anthropic API ключ (Подключения)."
          : "Не удалось получить разбор.",
        strengths: [], weaknesses: [], suggestions: [],
      });
    }
    setReviewing(false);
  };

  return (
    <div className="space-y-6">
      {stats && (
        <div className="grid grid-cols-6 gap-3">
          <Kpi label="Win Rate" value={stats.win_rate != null ? `${stats.win_rate}%` : "—"}
               sub={`${stats.wins}W / ${stats.losses}L`} />
          <Kpi label="Profit Factor" value={stats.profit_factor?.toFixed(2) ?? "—"} />
          <Kpi label="Матожидание" value={stats.expectancy != null ? fmtMoney2(stats.expectancy) : "—"} sub="на сделку" />
          <Kpi label="Ср. прибыль / убыток" value={`${fmtMoney2(stats.avg_win)} / ${fmtMoney2(stats.avg_loss)}`}
               sub={stats.avg_rr_realized != null ? `факт. R:R ${stats.avg_rr_realized}` : undefined} />
          <Kpi label="Макс. просадка" value={`${stats.max_drawdown_pct}%`}
               sub={`серии: ${stats.max_win_streak}W / ${stats.max_loss_streak}L`} />
          <Kpi label="Лучший / худший день" value={stats.best_day ? fmtMoney2(stats.best_day.money) : "—"}
               sub={stats.worst_day ? `${fmtMoney2(stats.worst_day.money)} (${stats.worst_day.date})` : undefined} />
        </div>
      )}

      {stats && stats.closed > 0 && (
        <div className="grid grid-cols-4 gap-6">
          <Breakdown title="По стратегиям" data={stats.by_strategy} />
          <Breakdown title="По инструментам" data={stats.by_instrument} />
          <Breakdown title="По сессиям" data={stats.by_session} />
          <Breakdown title="По дням недели" data={stats.by_weekday} />
        </div>
      )}

      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="pt-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold tracking-tight">ИИ-разбор журнала</h3>
            <Button size="sm" variant="outline" className="rounded-xl"
                    onClick={runReview} disabled={reviewing || !aiEnabled || closed.length === 0}>
              {reviewing ? "Анализирую…" : "Разобрать журнал"}
            </Button>
          </div>
          {!review ? (
            <p className="text-xs text-muted-foreground">
              ИИ найдёт сильные стороны, повторяющиеся ошибки и даст конкретные
              улучшения. Выводы сохраняются в память и учитываются в будущих оценках.
            </p>
          ) : (
            <div className="grid grid-cols-3 gap-4 text-xs">
              <ReviewCol title="Сильные стороны" items={review.strengths} tone="up" />
              <ReviewCol title="Слабые места" items={review.weaknesses} tone="down" />
              <ReviewCol title="Рекомендации" items={review.suggestions} />
              <p className="col-span-3 rounded-xl bg-black/[0.02] p-3 leading-relaxed">{review.summary}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="pt-4">
          <h3 className="mb-2 text-sm font-semibold tracking-tight">
            Закрытые сделки — стратегия и заметки
          </h3>
          {closed.length === 0 ? (
            <p className="py-4 text-center text-xs text-muted-foreground">
              Закрытых сделок пока нет.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Инструмент</TableHead>
                  <TableHead className="text-right">P&L, €</TableHead>
                  <TableHead className="w-[140px]">Стратегия</TableHead>
                  <TableHead>Заметки</TableHead>
                  <TableHead className="w-[90px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {closed.slice(0, 30).map((s) => {
                  const e = edit[s.id] ?? { strategy: s.strategy ?? "", notes: s.notes ?? "" };
                  const dirty = edit[s.id] != null;
                  return (
                    <TableRow key={s.id}>
                      <TableCell className="text-xs text-muted-foreground">#{s.id}</TableCell>
                      <TableCell className="text-xs font-medium">
                        {pretty(s.instrument)} · {s.timeframe} · {s.direction}
                        {s.partial_taken ? <span className="ml-1 text-[9px] text-[#0a84ff]">частич.</span> : null}
                      </TableCell>
                      <TableCell className={`text-right text-xs tabular-nums ${
                        (s.pnl_money ?? 0) >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                        {s.pnl_money != null ? fmtMoney2(s.pnl_money) : "—"}
                      </TableCell>
                      <TableCell>
                        <Input className="h-7 rounded-lg text-xs" placeholder="напр. trend-follow"
                               value={e.strategy}
                               onChange={(ev) => setEdit((m) => ({ ...m, [s.id]: { ...e, strategy: ev.target.value } }))} />
                      </TableCell>
                      <TableCell>
                        <Input className="h-7 rounded-lg text-xs" placeholder="что пошло так/не так…"
                               value={e.notes}
                               onChange={(ev) => setEdit((m) => ({ ...m, [s.id]: { ...e, notes: ev.target.value } }))} />
                      </TableCell>
                      <TableCell>
                        {dirty && (
                          <Button size="sm" className="h-7 rounded-lg text-xs" onClick={() => save(s.id)}>
                            Сохранить
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardContent className="pt-4">
        <p className="text-[10px] text-muted-foreground">{label}</p>
        <p className="text-base font-semibold tabular-nums tracking-tight">{value}</p>
        {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function Breakdown({ title, data }: { title: string; data: Record<string, { count: number; wins: number; money: number; win_rate: number | null }> }) {
  const rows = Object.entries(data).slice(0, 6);
  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardContent className="pt-4">
        <p className="mb-2 text-[11px] font-medium text-muted-foreground">{title}</p>
        <div className="space-y-1">
          {rows.map(([k, b]) => (
            <div key={k} className="flex items-center justify-between text-xs">
              <span className="truncate">{k}</span>
              <span className="ml-2 shrink-0 tabular-nums">
                <span className="text-muted-foreground">{b.win_rate ?? 0}% · </span>
                <span className={b.money >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}>
                  {fmtMoney2(b.money)}
                </span>
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ReviewCol({ title, items, tone }: { title: string; items: string[]; tone?: "up" | "down" }) {
  return (
    <div>
      <p className={`mb-1 font-semibold ${tone === "up" ? "text-[#34c759]" : tone === "down" ? "text-[#ff3b30]" : "text-[#0a84ff]"}`}>
        {title}
      </p>
      <ul className="space-y-1">
        {items.length === 0 && <li className="text-muted-foreground">—</li>}
        {items.map((s, i) => <li key={i} className="leading-snug">• {s}</li>)}
      </ul>
    </div>
  );
}
