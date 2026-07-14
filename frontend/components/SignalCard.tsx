"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { Analysis } from "@/lib/api";
import { fmtMoney2, pretty } from "@/lib/api";

function Row({ label, value, mono = true }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-sm font-medium ${mono ? "tabular-nums" : ""}`}>{value}</span>
    </div>
  );
}

export function SignalCard({
  analysis,
  onGenerate,
  generating,
  lastResult,
}: {
  analysis: Analysis | null;
  onGenerate: () => void;
  generating: boolean;
  lastResult: string | null;
}) {
  if (!analysis) return null;
  const { direction, levels, risk, confidence } = analysis;

  const dirStyles =
    direction === "BUY"
      ? "bg-[#34c759] text-white"
      : direction === "SELL"
        ? "bg-[#ff3b30] text-white"
        : "bg-muted text-muted-foreground";
  const dirLabel = direction === "BUY" ? "ПОКУПКА" : direction === "SELL" ? "ПРОДАЖА" : "ОЖИДАНИЕ";

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold tracking-tight">
            Рекомендация
          </CardTitle>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${dirStyles}`}>
            {dirLabel}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          {pretty(analysis.instrument)} · {analysis.timeframe} · уверенность{" "}
          {(confidence * 100).toFixed(0)}% ·{" "}
          {analysis.regime === "trending" ? "тренд" : "флэт"}
        </p>
      </CardHeader>
      <CardContent>
        <Row label="Вход" value={levels.entry} />
        <Row
          label="Стоп-лосс"
          value={<span className="text-[#ff3b30]">{levels.stop_loss} · {risk.sl_pips} п.</span>}
        />
        <Row
          label="Тейк-профит"
          value={<span className="text-[#34c759]">{levels.take_profit} · {risk.tp_pips} п.</span>}
        />
        <Row label="Риск / прибыль" value={`1 : ${analysis.risk_reward}`} />
        <Separator className="my-2" />
        <Row
          label="Риск в деньгах"
          value={<span className="text-[#ff3b30]">−{fmtMoney2(risk.risk_amount)}</span>}
        />
        <Row
          label="Потенциальная прибыль"
          value={<span className="text-[#34c759]">+{fmtMoney2(risk.potential_profit)}</span>}
        />
        <Row label="Объём позиции" value={`${risk.units.toLocaleString("ru-RU")} ед.`} />
        <Row
          label="Метод расчёта"
          value={risk.sizing_used === "half_kelly"
            ? `½ Келли (WR ${risk.kelly_win_rate}%)`
            : "фикс. % риска"}
          mono={false}
        />

        {!risk.approved && direction !== "HOLD" && (
          <div className="mt-3 rounded-xl bg-amber-50 p-3 text-xs text-amber-900">
            <p className="font-medium">Риск-менеджер отклонил сигнал:</p>
            <ul className="mt-1 list-inside list-disc">
              {risk.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}
        {direction === "HOLD" && (
          <div className="mt-3 rounded-xl bg-muted/60 p-3 text-xs text-muted-foreground">
            Сейчас нет статистического преимущества — оценка{" "}
            {analysis.score >= 0 ? "+" : ""}
            {analysis.score.toFixed(2)} в нейтральной зоне. Уровни показаны
            гипотетически, по направлению наклона.
          </div>
        )}

        <Button
          className="mt-4 w-full rounded-xl"
          disabled={generating || !risk.approved}
          onClick={onGenerate}
        >
          {generating ? "Сохраняю…" : "Отслеживать сигнал"}
        </Button>
        {lastResult && (
          <p className="mt-2 text-center text-xs text-muted-foreground">{lastResult}</p>
        )}
        <p className="mt-3 text-center text-[10px] leading-4 text-muted-foreground">
          Поддержка решений — не финансовый совет.
        </p>
      </CardContent>
    </Card>
  );
}
