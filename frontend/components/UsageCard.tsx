"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { UsageStats } from "@/lib/api";

const PURPOSE_LABEL: Record<string, string> = {
  triage: "Отбор новостей (Haiku)",
  debate: "Дебаты быки/медведи (Sonnet)",
  pair_bias: "Уклон по парам (Sonnet)",
  chat: "Чат-ассистент (Sonnet)",
  news_intel: "Новости по символу (Sonnet)",
  journal_review: "Разбор журнала (Sonnet)",
  memory: "Консолидация памяти (Sonnet)",
  backtest_analysis: "Анализ бэктеста (Sonnet)",
};

export function UsageCard({ usage }: { usage: UsageStats | null }) {
  if (!usage) return null;
  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold tracking-tight">
          Расход Anthropic API
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Токены и оценка стоимости · сегодня и за 30 дней
        </p>
      </CardHeader>
      <CardContent>
        <div className="mb-3 grid grid-cols-2 gap-2">
          <div className="rounded-xl bg-muted/50 p-3">
            <p className="text-[11px] text-muted-foreground">Сегодня</p>
            <p className="text-base font-semibold tabular-nums">
              {usage.today.cost_eur.toFixed(3)} €
            </p>
            <p className="text-[11px] text-muted-foreground">
              {usage.today.calls} вызов(ов) ·{" "}
              {(usage.today.input_tokens + usage.today.output_tokens).toLocaleString("ru-RU")} ток.
            </p>
          </div>
          <div className="rounded-xl bg-muted/50 p-3">
            <p className="text-[11px] text-muted-foreground">30 дней</p>
            <p className="text-base font-semibold tabular-nums">
              {usage.last_30d.cost_eur.toFixed(3)} €
            </p>
            <p className="text-[11px] text-muted-foreground">
              {usage.last_30d.calls} вызов(ов) ·{" "}
              {(usage.last_30d.input_tokens + usage.last_30d.output_tokens).toLocaleString("ru-RU")} ток.
            </p>
          </div>
        </div>
        {usage.recent.length > 0 ? (
          <ul className="space-y-1.5">
            {usage.recent.slice(0, 6).map((u, i) => (
              <li key={i} className="flex justify-between text-xs">
                <span className="text-muted-foreground">
                  {PURPOSE_LABEL[u.purpose] ?? u.purpose}
                  <span className="ml-1 text-[10px] text-muted-foreground/60">
                    {new Date(u.created_at).toLocaleString("ru-RU", {
                      day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
                    })}
                  </span>
                </span>
                <span className="tabular-nums">
                  {u.input_tokens + u.output_tokens} ток. · {u.cost_eur.toFixed(4)} €
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded-xl bg-muted/50 p-3 text-center text-xs text-muted-foreground">
            Вызовов ещё не было. ИИ-анализ запускается по расписанию или вручную.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
