"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, pretty, type PatternsResult, type SymbolNews } from "@/lib/api";

const DIR_COLOR: Record<string, string> = {
  bullish: "bg-[#34c759]/10 text-[#34c759]",
  bearish: "bg-[#ff3b30]/10 text-[#ff3b30]",
  neutral: "bg-black/5 text-muted-foreground",
};

const SENT_COLOR: Record<string, string> = {
  positive: "text-[#34c759]",
  negative: "text-[#ff3b30]",
  neutral: "text-muted-foreground",
};

export function PatternsPanel({ instrument, patterns, aiEnabled }: {
  instrument: string | null;
  patterns: PatternsResult | null;
  aiEnabled: boolean;
}) {
  const [news, setNews] = useState<SymbolNews | null>(null);
  const [loadingNews, setLoadingNews] = useState(false);
  const [newsError, setNewsError] = useState<string | null>(null);

  const loadNews = async () => {
    if (!instrument) return;
    setLoadingNews(true);
    setNewsError(null);
    try {
      setNews(await api.symbolNews(instrument));
    } catch (e) {
      setNewsError(e instanceof Error && e.message.includes("400")
        ? "Нужен Anthropic API ключ (Подключения)."
        : "Не удалось получить новостной анализ.");
    }
    setLoadingNews(false);
  };

  return (
    <div className="grid grid-cols-2 gap-6">
      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="pt-4">
          <h3 className="mb-2 text-sm font-semibold tracking-tight">
            Паттерны {instrument ? `· ${pretty(instrument)}` : ""}
          </h3>
          {!patterns || patterns.patterns.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">
              Явных графических паттернов не обнаружено. Зоны S/R и трендовые
              линии отображаются на графике (тумблер «Уровни»).
            </p>
          ) : (
            <div className="space-y-2">
              {patterns.patterns.map((p, i) => (
                <div key={i} className="rounded-xl bg-black/[0.02] p-3">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-semibold">{p.name}</p>
                    <Badge variant="secondary" className={`rounded-full text-[9px] ${DIR_COLOR[p.direction]}`}>
                      {p.direction === "bullish" ? "бычий" : p.direction === "bearish" ? "медвежий" : "нейтральный"}
                    </Badge>
                    <Badge variant="secondary" className="rounded-full text-[9px]">
                      {p.status === "confirmed" ? "подтверждён" : "формируется"}
                    </Badge>
                    <span className="ml-auto text-[10px] tabular-nums text-muted-foreground">
                      {(p.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    {p.explanation}
                  </p>
                </div>
              ))}
            </div>
          )}
          {patterns && patterns.sr_zones.length > 0 && (
            <div className="mt-3">
              <p className="mb-1 text-[11px] font-medium text-muted-foreground">Зоны S/R</p>
              <div className="flex flex-wrap gap-1.5">
                {patterns.sr_zones.map((z, i) => (
                  <span key={i} className={`rounded-lg px-2 py-0.5 text-[10px] tabular-nums ${
                    z.kind === "support" ? "bg-[#34c759]/10 text-[#34c759]" : "bg-[#ff3b30]/10 text-[#ff3b30]"
                  }`}>
                    {z.price} · {z.touches}×
                  </span>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="pt-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold tracking-tight">
              Новости по инструменту
            </h3>
            <Button size="sm" variant="outline" className="rounded-xl"
                    onClick={loadNews} disabled={!instrument || loadingNews || !aiEnabled}>
              {loadingNews ? "Анализирую…" : "Проанализировать"}
            </Button>
          </div>
          {newsError && <p className="text-xs text-[#ff3b30]">{newsError}</p>}
          {!news && !newsError && (
            <p className="py-6 text-center text-xs text-muted-foreground">
              {aiEnabled
                ? "ИИ отберёт релевантные заголовки, оценит тональность и объяснит, почему каждая новость важна."
                : "Нужен Anthropic API ключ — введите его в «Подключениях»."}
            </p>
          )}
          {news && (
            <div className="space-y-2">
              <p className={`text-xs font-medium ${SENT_COLOR[news.overall_sentiment]}`}>
                {news.overall_sentiment === "positive" ? "▲ Позитивный фон" :
                 news.overall_sentiment === "negative" ? "▼ Негативный фон" : "◆ Нейтральный фон"}
              </p>
              <p className="text-xs leading-relaxed">{news.summary}</p>
              <div className="space-y-1.5">
                {news.items.map((it, i) => (
                  <div key={i} className="rounded-xl bg-black/[0.02] p-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[11px] font-medium leading-snug">{it.headline}</p>
                      <span className={`shrink-0 text-[10px] tabular-nums ${SENT_COLOR[it.sentiment]}`}>
                        {it.sentiment === "positive" ? "+" : it.sentiment === "negative" ? "−" : "·"}
                        {(it.impact * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="mt-0.5 text-[10px] text-muted-foreground">{it.why}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
