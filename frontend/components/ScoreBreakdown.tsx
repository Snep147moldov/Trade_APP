"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Analysis } from "@/lib/api";

const LABELS: Record<string, string> = {
  trend: "Тренд (EMA 20/50 к ATR)",
  tsmom: "Моментум врем. рядов (20 бар)",
  kama_er: "Коэф. эффективности Кауфмана",
  macd: "Гистограмма MACD",
  rsi: "RSI 14",
  stoch: "Стохастик 14,3,3",
  bollinger: "Боллинджер %B (возврат)",
  roc: "Скорость изменения 10",
  htf_trend: "Старший таймфрейм · тренд",
  ai_news: "ИИ · новостной фон",
  ai_prediction: "ИИ · прогнозный уклон",
};

export function ScoreBreakdown({ analysis }: { analysis: Analysis | null }) {
  if (!analysis) return null;
  const entries = Object.entries(analysis.components);

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex items-baseline justify-between">
          <CardTitle className="text-base font-semibold tracking-tight">
            Совокупная оценка
          </CardTitle>
          <span
            className={`text-lg font-semibold tabular-nums ${
              analysis.score > 0 ? "text-[#34c759]" : analysis.score < 0 ? "text-[#ff3b30]" : ""
            }`}
          >
            {analysis.score >= 0 ? "+" : ""}
            {analysis.score.toFixed(2)}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          Взвешенная сумма нормированных факторов · доля ИИ ограничена{" "}
          {((analysis.weights.ai_news + analysis.weights.ai_prediction) * 100).toFixed(0)}% ·
          режим: {analysis.regime === "trending" ? "тренд" : "флэт"} (Hurst{" "}
          {analysis.indicators.hurst})
        </p>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {entries.map(([key, value]) => {
          const weight = analysis.weights[key] ?? 0;
          const contribution = value * weight;
          const pct = Math.min(100, Math.abs(value) * 100);
          return (
            <div key={key}>
              <div className="mb-1 flex justify-between text-xs">
                <span className="text-muted-foreground">
                  {LABELS[key] ?? key}
                  <span className="ml-1 text-[10px] text-muted-foreground/60">
                    вес {(weight * 100).toFixed(0)}%
                  </span>
                </span>
                <span className="font-medium tabular-nums">
                  {contribution >= 0 ? "+" : ""}
                  {contribution.toFixed(3)}
                </span>
              </div>
              <div className="flex h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="flex w-1/2 justify-end">
                  {value < 0 && (
                    <div
                      className="h-full rounded-l-full bg-[#ff3b30]"
                      style={{ width: `${pct}%` }}
                    />
                  )}
                </div>
                <div className="w-1/2">
                  {value > 0 && (
                    <div
                      className="h-full rounded-r-full bg-[#34c759]"
                      style={{ width: `${pct}%` }}
                    />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
