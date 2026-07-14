"use client";

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
import { fmtMoney2, pretty } from "@/lib/api";

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

export function HistoryTable({
  signals,
  stats,
  onEvaluate,
  evaluating,
}: {
  signals: SignalRow[];
  stats: SignalStats | null;
  onEvaluate: () => void;
  evaluating: boolean;
}) {
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
              </TableRow>
            </TableHeader>
            <TableBody>
              {signals.map((s) => (
                <TableRow key={s.id} className="text-sm">
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
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
