"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { NewsResult } from "@/lib/api";

export function NewsPanel({
  news,
  onRun,
  running,
}: {
  news: NewsResult | null;
  onRun: () => void;
  running: boolean;
}) {
  if (!news) return null;
  const entries = Object.entries(news.vector);
  const updated = news.created_at
    ? new Date(news.created_at).toLocaleString("ru-RU", {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
      })
    : null;

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold tracking-tight">
            Новостной анализ
          </CardTitle>
          <div className="flex items-center gap-2">
            {!news.enabled && (
              <Badge variant="secondary" className="rounded-full text-[10px]">
                ИИ выключен
              </Badge>
            )}
            {news.enabled && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 rounded-xl text-xs"
                onClick={onRun}
                disabled={running}
              >
                {running ? "Анализирую…" : "Запустить сейчас"}
              </Button>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {updated
            ? `Обновлено ${updated} · по расписанию: ${news.news_times.join(", ")} UTC`
            : `Запуски по расписанию: ${news.news_times.join(", ")} UTC`}
        </p>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-xs leading-5">{news.summary}</p>

        {(news.bull_case || news.bear_case) && (
          <div className="mb-3 grid grid-cols-2 gap-2">
            <div className="rounded-xl bg-[#34c759]/5 p-2.5">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#34c759]">
                Аргументы быков
              </p>
              <p className="text-[11px] leading-4 text-muted-foreground">{news.bull_case}</p>
            </div>
            <div className="rounded-xl bg-[#ff3b30]/5 p-2.5">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#ff3b30]">
                Аргументы медведей
              </p>
              <p className="text-[11px] leading-4 text-muted-foreground">{news.bear_case}</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-4 gap-2">
          {entries.map(([ccy, val]) => (
            <div
              key={ccy}
              className="rounded-xl bg-muted/50 px-2 py-2 text-center"
              title={news.rationales[ccy] ?? ""}
            >
              <div className="text-xs font-semibold">{ccy}</div>
              <div
                className={`text-sm font-medium tabular-nums ${
                  val > 0.05 ? "text-[#34c759]" : val < -0.05 ? "text-[#ff3b30]" : "text-muted-foreground"
                }`}
              >
                {val >= 0 ? "+" : ""}
                {val.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
        {news.headlines.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {news.headlines.slice(0, 5).map((h) => (
              <li key={h} className="truncate text-xs text-muted-foreground">
                · {h}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
