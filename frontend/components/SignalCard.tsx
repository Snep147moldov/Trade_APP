"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import type { Analysis } from "@/lib/api";
import { fmtMoney2, pretty } from "@/lib/api";
import { tr } from "@/lib/i18n";

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
  signalMode = "conservative",
  onToggleMode,
  mt5Ready = false,
  mt5Lots,
  onMt5Trade,
}: {
  analysis: Analysis | null;
  onGenerate: () => void;
  generating: boolean;
  lastResult: string | null;
  signalMode?: "conservative" | "aggressive";
  onToggleMode?: (aggressive: boolean) => Promise<void>;
  mt5Ready?: boolean;
  mt5Lots?: number;
  onMt5Trade?: (orders: number) => Promise<string>;
}) {
  const [switching, setSwitching] = useState(false);
  const [trading, setTrading] = useState(false);
  const [mt5Result, setMt5Result] = useState<string | null>(null);
  const [mt5Orders, setMt5Orders] = useState(1);

  const tradeMt5 = async () => {
    if (!onMt5Trade) return;
    setTrading(true);
    setMt5Result(null);
    try {
      setMt5Result(await onMt5Trade(mt5Orders));
    } catch (e) {
      setMt5Result(tr("❌ {0}", e instanceof Error ? e.message.slice(0, 120) : "ошибка MT5"));
    }
    setTrading(false);
  };
  if (!analysis) return null;
  const { direction, levels, risk, confidence } = analysis;
  const aggressiveOn = signalMode === "aggressive";
  const aggressiveDir = analysis.score >= 0 ? tr("ПОКУПКА") : tr("ПРОДАЖА");

  const toggleMode = async (v: boolean) => {
    if (!onToggleMode) return;
    setSwitching(true);
    try {
      await onToggleMode(v);
    } finally {
      setSwitching(false);
    }
  };

  const dirStyles =
    direction === "BUY"
      ? "bg-pos text-white"
      : direction === "SELL"
        ? "bg-neg text-white"
        : "bg-muted text-muted-foreground";
  const dirLabel = direction === "BUY" ? tr("ПОКУПКА") : direction === "SELL" ? tr("ПРОДАЖА") : tr("ОЖИДАНИЕ");

  return (
    <Card className="rounded-2xl border-border shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold tracking-tight">
            {tr("Рекомендация")}
          </CardTitle>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${dirStyles}`}>
            {dirLabel}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          {pretty(analysis.instrument)} · {analysis.timeframe} {tr("· сила сигнала (не вероятность)")}{" "}
          {(confidence * 100).toFixed(0)}% ·{" "}
          {analysis.regime === "trending" ? tr("тренд") : tr("флэт")}
        </p>
        {analysis.live && (
          <p className="flex items-center gap-1.5 text-xs tabular-nums">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand/60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-brand" />
            </span>
            <span className="text-muted-foreground">{tr("LIVE (свеча формируется):")}</span>
            <span className={`font-semibold ${
              analysis.live.score >= 0 ? "text-pos" : "text-neg"}`}>
              {analysis.live.direction} {analysis.live.score >= 0 ? "+" : ""}
              {analysis.live.score.toFixed(3)}
            </span>
            <span className="text-muted-foreground">
              {tr("· подтв.")} {analysis.score >= 0 ? "+" : ""}{analysis.score.toFixed(3)}
            </span>
          </p>
        )}
        {analysis.mode === "aggressive" && analysis.below_threshold && (
          <p className="rounded-lg bg-warn/10 px-2 py-1 text-[13px] sm:text-[11px] text-warn">
            {tr("⚡ Агрессивный режим: оценка ниже порога — статистическое преимущество не подтверждено, размер позиции ×0.5")}
          </p>
        )}
      </CardHeader>
      <CardContent>
        <Row label={tr("Вход")} value={levels.entry} />
        <Row
          label={tr("Стоп-лосс")}
          value={<span className="text-neg">{levels.stop_loss} · {risk.sl_pips} {tr("п.")}</span>}
        />
        <Row
          label={tr("Тейк-профит")}
          value={<span className="text-pos">{levels.take_profit} · {risk.tp_pips} {tr("п.")}</span>}
        />
        <Row label={tr("Риск / прибыль")} value={`1 : ${analysis.risk_reward}`} />
        <Separator className="my-2" />
        <Row
          label={tr("Риск в деньгах")}
          value={<span className="text-neg">−{fmtMoney2(risk.risk_amount)}</span>}
        />
        <Row
          label={tr("Потенциальная прибыль")}
          value={<span className="text-pos">+{fmtMoney2(risk.potential_profit)}</span>}
        />
        <Row label={tr("Объём позиции")} value={tr("{0} ед.", risk.units.toLocaleString("ru-RU"))} />
        <Row
          label={tr("Метод расчёта")}
          value={risk.sizing_used === "half_kelly"
            ? tr("½ Келли (WR {0}%)", risk.kelly_win_rate)
            : tr("фикс. % риска")}
          mono={false}
        />

        {!risk.approved && direction !== "HOLD" && (
          <div className="mt-3 rounded-xl bg-warn/10 p-3 text-xs text-warn">
            <p className="font-medium">{tr("Риск-менеджер отклонил сигнал:")}</p>
            <ul className="mt-1 list-inside list-disc">
              {risk.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}
        {direction === "HOLD" && (
          <div className="mt-3 rounded-xl bg-muted/60 p-3 text-xs text-muted-foreground">
            {tr("Сейчас нет статистического преимущества — оценка")}{" "}
            {analysis.score >= 0 ? "+" : ""}
            {analysis.score.toFixed(2)} {tr("в нейтральной зоне. Уровни показаны гипотетически, по направлению наклона.")}
          </div>
        )}

        <Button
          className="mt-4 w-full rounded-xl"
          disabled={generating || !risk.approved || (aggressiveOn && analysis.below_threshold)}
          onClick={onGenerate}
        >
          {generating ? tr("Сохраняю…") : tr("Отслеживать сигнал")}
        </Button>

        {onToggleMode && (
          <div className="mt-2 flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2">
            <div>
              <p className="text-xs font-medium">{tr("⚡ Агрессивный режим")}</p>
              <p className="text-xs sm:text-[10px] text-muted-foreground">
                {tr("Всегда покупка/продажа по знаку оценки")}
              </p>
            </div>
            <Switch checked={aggressiveOn} disabled={switching}
                    onCheckedChange={toggleMode} />
          </div>
        )}
        {aggressiveOn && (
          <Button
            className={`mt-2 w-full rounded-xl ${
              analysis.score >= 0
                ? "bg-pos hover:bg-pos"
                : "bg-neg hover:bg-neg"
            } text-white`}
            disabled={generating || !risk.approved}
            onClick={onGenerate}
          >
            {generating
              ? tr("Сохраняю…")
              : tr("⚡ {0} агрессивно{1}", aggressiveDir, analysis.below_threshold ? " · размер ×0.5" : "")}
          </Button>
        )}

        {mt5Ready && onMt5Trade && (
          <div className="mt-2 flex w-full gap-2">
            <Button
              variant="outline"
              className="min-w-0 flex-1 rounded-xl border-brand/40 text-brand-ink hover:bg-brand/10"
              disabled={trading || generating || direction === "HOLD" || !risk.approved}
              onClick={tradeMt5}
            >
              <span className="truncate">
                {trading
                  ? tr("Отправляю ордер…")
                  : tr("MT5 · {0}{1}{2}", dirLabel, mt5Lots ? ` · ${mt5Lots} лот` : "", mt5Orders > 1 ? ` ×${mt5Orders}` : "")}
              </span>
            </Button>
            <select
              title={tr("Сколько ордеров открыть по этому сигналу (тейки ступенями: +1R, цель, дальше)")}
              className="h-9 w-16 shrink-0 rounded-xl border border-brand/40 bg-transparent px-2 text-sm text-brand-ink"
              value={mt5Orders}
              disabled={trading}
              onChange={(e) => setMt5Orders(parseInt(e.target.value, 10))}
            >
              {[1, 2, 3].map((n) => (
                <option key={n} value={n}>
                  ×{n}
                </option>
              ))}
            </select>
          </div>
        )}
        {mt5Result && (
          <p className="mt-2 text-center text-xs text-muted-foreground">{mt5Result}</p>
        )}
        {lastResult && (
          <p className="mt-2 text-center text-xs text-muted-foreground">{lastResult}</p>
        )}
        <p className="mt-3 text-center text-xs sm:text-[10px] leading-4 text-muted-foreground">
          {tr("Поддержка решений — не финансовый совет.")}
        </p>
      </CardContent>
    </Card>
  );
}
