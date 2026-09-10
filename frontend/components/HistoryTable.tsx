"use client";

import { useMemo, useState } from "react";
import { ArrowDownUp, Filter } from "lucide-react";
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
  open: "bg-brand/10 text-brand-ink",
  hit_tp: "bg-pos/10 text-pos",
  hit_sl: "bg-neg/10 text-neg",
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

function Pick({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <select
      className="h-7 rounded-lg border bg-transparent px-2 text-[11px]"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </select>
  );
}

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
  // Отбор и сортировка. Раньше история была одной лентой по дням: чтобы
  // найти все убыточные сделки по одной паре, приходилось листать вручную.
  const [fStatus, setFStatus] = useState("all");
  const [fTf, setFTf] = useState("all");
  const [fSym, setFSym] = useState("all");
  const [fSide, setFSide] = useState("all");
  const [sortKey, setSortKey] = useState("date");
  const [asc, setAsc] = useState(false);
  const [clearMode, setClearMode] = useState("closed");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const money = (r: SignalRow) => r.mt5_pnl ?? r.pnl_money ?? 0;
  const rMultiple = (r: SignalRow) =>
    r.risk_amount ? money(r) / r.risk_amount : 0;

  const symbols = useMemo(
    () => [...new Set(signals.map((s) => s.instrument))].sort(),
    [signals],
  );
  const timeframes = useMemo(
    () => [...new Set(signals.map((s) => s.timeframe))].sort(),
    [signals],
  );

  const view = useMemo(() => {
    let rows = signals;
    if (fStatus === "wins") rows = rows.filter((r) => money(r) > 0 && r.status !== "open");
    else if (fStatus === "losses") rows = rows.filter((r) => money(r) < 0 && r.status !== "open");
    else if (fStatus !== "all") rows = rows.filter((r) => r.status === fStatus);
    if (fTf !== "all") rows = rows.filter((r) => r.timeframe === fTf);
    if (fSym !== "all") rows = rows.filter((r) => r.instrument === fSym);
    if (fSide !== "all") rows = rows.filter((r) => r.direction === fSide);

    const cmp: Record<string, (a: SignalRow, b: SignalRow) => number> = {
      date: (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at),
      money: (a, b) => money(a) - money(b),
      r: (a, b) => rMultiple(a) - rMultiple(b),
      score: (a, b) => Math.abs(a.score) - Math.abs(b.score),
      instrument: (a, b) => a.instrument.localeCompare(b.instrument),
    };
    const sorted = [...rows].sort(cmp[sortKey] ?? cmp.date);
    return asc ? sorted : sorted.reverse();
  }, [signals, fStatus, fTf, fSym, fSide, sortKey, asc]);

  // сумма по текущему отбору — главный смысл фильтра: видно, сколько принесла
  // именно эта выборка, а не вся история
  const viewTotal = view.reduce((t, r) => t + money(r), 0);
  const viewClosed = view.filter((r) => r.status !== "open").length;

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
    <Card className="rounded-2xl border-border shadow-sm">
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
                <b className={stats.total_money >= 0 ? "text-pos" : "text-neg"}>
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
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
              <Filter className="h-3 w-3" /> Отбор
            </span>
            <Pick
              value={fStatus}
              onChange={setFStatus}
              options={[
                ["all", "Все"],
                ["wins", "Прибыльные"],
                ["losses", "Убыточные"],
                ["open", "Открытые"],
                ["hit_tp", "По цели"],
                ["hit_sl", "По стопу"],
                ["expired", "По сроку"],
              ]}
            />
            <Pick
              value={fSide}
              onChange={setFSide}
              options={[["all", "Обе стороны"], ["BUY", "Покупка"], ["SELL", "Продажа"]]}
            />
            <Pick
              value={fTf}
              onChange={setFTf}
              options={[["all", "Все ТФ"], ...timeframes.map((t) => [t, t] as [string, string])]}
            />
            <Pick
              value={fSym}
              onChange={setFSym}
              options={[
                ["all", "Все пары"],
                ...symbols.map((t) => [t, pretty(t)] as [string, string]),
              ]}
            />
            <span className="ml-2 inline-flex items-center gap-1 text-[11px] text-muted-foreground">
              <ArrowDownUp className="h-3 w-3" /> Сортировка
            </span>
            <Pick
              value={sortKey}
              onChange={setSortKey}
              options={[
                ["date", "По дате"],
                ["money", "По деньгам"],
                ["r", "По R"],
                ["score", "По оценке"],
                ["instrument", "По паре"],
              ]}
            />
            <button
              type="button"
              onClick={() => setAsc((v) => !v)}
              className="h-7 rounded-lg border px-2 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
              title={asc ? "По возрастанию" : "По убыванию"}
            >
              {asc ? "↑ возр." : "↓ убыв."}
            </button>
            <span className="text-[11px] tabular-nums text-muted-foreground">
              {view.length} сигн. · {viewClosed} закрыто ·{" "}
              <span className={viewTotal >= 0 ? "text-pos" : "text-neg"}>
                {viewTotal >= 0 ? "+" : ""}
                {viewTotal.toFixed(2)} €
              </span>
            </span>
          </div>
        )}
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
                confirming ? "border-neg/50 text-neg" : "text-muted-foreground"
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
              {(() => {
                const rowFor = (s: SignalRow) => (
                <TableRow key={s.id} className="group text-sm">
                  <TableCell className="font-medium">{pretty(s.instrument)}</TableCell>
                  <TableCell>{s.timeframe}</TableCell>
                  <TableCell>
                    <span
                      className={
                        s.direction === "BUY" ? "text-pos" : "text-neg"
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
                      <span className={s.pnl_pips >= 0 ? "text-pos" : "text-neg"}>
                        {s.pnl_pips >= 0 ? "+" : ""}
                        {s.pnl_pips}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {s.pnl_money == null ? "—" : (
                      <span className={s.pnl_money >= 0 ? "text-pos" : "text-neg"}>
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
                        <span className="text-[10px] text-brand-ink">×{s.mt5_orders} откр.</span>
                      ) : "—"
                    ) : (
                      <span className={s.mt5_pnl >= 0 ? "text-pos" : "text-neg"}>
                        {s.mt5_pnl >= 0 ? "+" : ""}
                        {s.mt5_pnl.toFixed(2)}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <button
                      title={`Удалить сигнал #${s.id}`}
                      className="rounded-md px-1.5 py-0.5 text-xs text-muted-foreground opacity-0 transition-opacity hover:bg-neg/10 hover:text-neg group-hover:opacity-100 disabled:opacity-40"
                      disabled={deletingId === s.id}
                      onClick={() => deleteOne(s.id)}
                    >
                      ✕
                    </button>
                  </TableCell>
                </TableRow>
                );
                return (sortKey === "date"
                  ? groupByDay(view)
                  : [{ key: "flat", rows: view }]
                ).map((g) => {
                const closed = g.rows.filter((s) => s.pnl_money != null);
                const dayMoney = closed.reduce((sum, s) => sum + (s.pnl_money ?? 0), 0);
                if (g.key === "flat") {
                  // при сортировке не по дате шапки дней только мешают
                  return g.rows.map((s) => rowFor(s));
                }
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
                        <span className={dayMoney >= 0 ? "text-pos" : "text-neg"}>
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
                          <span className={m >= 0 ? "text-pos" : "text-neg"}>
                            {m >= 0 ? "+" : ""}
                            {m.toFixed(2)}
                          </span>
                        );
                      })()}
                    </TableCell>
                    <TableCell className="py-1.5" />
                  </TableRow>,
                  ...g.rows.map((s) => rowFor(s)),
                ];
                });
              })()}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
