"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CalendarEvent } from "@/lib/api";

const IMPACT_STYLE: Record<string, string> = {
  high: "bg-[#ff3b30]/10 text-[#ff3b30]",
  medium: "bg-[#ff9f0a]/10 text-[#ff9f0a]",
  low: "bg-muted text-muted-foreground",
};

const IMPACT_RU: Record<string, string> = {
  high: "высокое",
  medium: "среднее",
  low: "низкое",
};

function countdown(ts: number): string {
  const diff = ts - Math.floor(Date.now() / 1000);
  if (diff <= 0) return "идёт / прошло";
  const h = Math.floor(diff / 3600);
  const m = Math.floor((diff % 3600) / 60);
  if (h >= 24) return `через ${Math.floor(h / 24)} д ${h % 24} ч`;
  if (h > 0) return `через ${h} ч ${m} м`;
  return `через ${m} м`;
}

export function CalendarCard({ events }: { events: CalendarEvent[] }) {
  const upcoming = events
    .filter((e) => e.time >= Math.floor(Date.now() / 1000) - 1800)
    .sort((a, b) => Number(b.relevant) - Number(a.relevant) || a.time - b.time)
    .slice(0, 12);

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold tracking-tight">
          Экономический календарь
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Ставки, инфляция, CPI, NFP… · влияние высокое / среднее / низкое ·
          предупреждение за 30 минут по вашим инструментам
        </p>
      </CardHeader>
      <CardContent>
        {upcoming.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Ближайших событий нет (или календарь недоступен).
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="text-xs">
                <TableHead>Когда</TableHead>
                <TableHead>Валюта</TableHead>
                <TableHead>Событие</TableHead>
                <TableHead>Влияние</TableHead>
                <TableHead className="text-right">Прогноз</TableHead>
                <TableHead className="text-right">Пред.</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {upcoming.map((e, i) => (
                <TableRow key={i} className={`text-sm ${e.relevant ? "" : "opacity-50"}`}>
                  <TableCell className="whitespace-nowrap">
                    <div className="text-xs tabular-nums">
                      {new Date(e.time * 1000).toLocaleString("ru-RU", {
                        weekday: "short", hour: "2-digit", minute: "2-digit",
                      })}
                    </div>
                    <div className="text-[10px] text-muted-foreground">{countdown(e.time)}</div>
                  </TableCell>
                  <TableCell className="font-medium">{e.currency}</TableCell>
                  <TableCell className="max-w-[260px] truncate">{e.title}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={`rounded-full text-[10px] ${IMPACT_STYLE[e.impact]}`}>
                      {IMPACT_RU[e.impact]}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums">{e.forecast || "—"}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums text-muted-foreground">
                    {e.previous || "—"}
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
