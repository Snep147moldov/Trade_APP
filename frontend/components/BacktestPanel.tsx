"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { EquityChart } from "@/components/PriceChart";
import {
  api, fmtMoney2, pretty,
  type BacktestResult, type BacktestRunSummary,
} from "@/lib/api";

const TFS = ["1m", "5m", "15m", "40m", "1h", "4h", "1d"];

export function BacktestPanel({ instrument, watchlist, aiEnabled }: {
  instrument: string | null;
  watchlist: string[];
  aiEnabled: boolean;
}) {
  const [form, setForm] = useState({
    instrument: instrument ?? watchlist[0] ?? "EUR_USD",
    timeframe: "1h", bars: "1500", initial_equity: "10000",
    risk_per_trade_pct: "1", min_score: "0.30", risk_reward: "1.8",
    sl_atr_multiple: "1.5", spread_pips: "1", slippage_pips: "0.2",
    commission_eur: "0", walk_forward_folds: "0",
  });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshRuns = useCallback(async () => {
    try {
      setRuns((await api.backtestRuns()).runs);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refreshRuns();
  }, [refreshRuns]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const run = async () => {
    setBusy(true);
    setError(null);
    setAnalysis(null);
    try {
      const r = await api.runBacktest({
        instrument: form.instrument.toUpperCase().replace("/", "_"),
        timeframe: form.timeframe,
        bars: parseInt(form.bars) || 1500,
        initial_equity: parseFloat(form.initial_equity) || 10000,
        risk_per_trade_pct: parseFloat(form.risk_per_trade_pct) || 1,
        min_score: parseFloat(form.min_score) || 0.3,
        risk_reward: parseFloat(form.risk_reward) || 1.8,
        sl_atr_multiple: parseFloat(form.sl_atr_multiple) || 1.5,
        spread_pips: parseFloat(form.spread_pips) || 0,
        slippage_pips: parseFloat(form.slippage_pips) || 0,
        commission_eur: parseFloat(form.commission_eur) || 0,
        walk_forward_folds: parseInt(form.walk_forward_folds) || 0,
      });
      setResult(r);
      refreshRuns();
    } catch (e) {
      setError(e instanceof Error ? e.message.slice(0, 200) : "ошибка бэктеста");
    }
    setBusy(false);
  };

  const analyze = async () => {
    if (!result) return;
    setAnalyzing(true);
    try {
      setAnalysis((await api.analyzeBacktest(result.run_id)).analysis);
    } catch {
      setAnalysis("Не удалось получить ИИ-анализ.");
    }
    setAnalyzing(false);
  };

  const m = result?.metrics;

  const field = (k: keyof typeof form, label: string) => (
    <div className="space-y-1">
      <Label className="text-[11px]">{label}</Label>
      <Input className="h-8 rounded-xl text-xs" value={form[k]} onChange={set(k)} />
    </div>
  );

  return (
    <div className="space-y-6">
      <Card className="rounded-2xl border-black/5 shadow-sm">
        <CardContent className="pt-4">
          <h3 className="mb-3 text-sm font-semibold tracking-tight">Бэктест стратегии</h3>
          <div className="grid grid-cols-6 gap-3">
            <div className="space-y-1">
              <Label className="text-[11px]">Инструмент</Label>
              <Input className="h-8 rounded-xl text-xs" value={form.instrument}
                     onChange={set("instrument")} list="bt-symbols" />
              <datalist id="bt-symbols">
                {watchlist.map((w) => <option key={w} value={w} />)}
              </datalist>
            </div>
            <div className="space-y-1">
              <Label className="text-[11px]">Таймфрейм</Label>
              <select className="h-8 w-full rounded-xl border bg-transparent px-2 text-xs"
                      value={form.timeframe}
                      onChange={(e) => setForm((f) => ({ ...f, timeframe: e.target.value }))}>
                {TFS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            {field("bars", "Баров (300–5000)")}
            {field("initial_equity", "Капитал, €")}
            {field("risk_per_trade_pct", "Риск/сделка, %")}
            {field("min_score", "Порог оценки")}
            {field("risk_reward", "R:R")}
            {field("sl_atr_multiple", "SL, ×ATR")}
            {field("spread_pips", "Спред, п.")}
            {field("slippage_pips", "Проскальз., п.")}
            {field("commission_eur", "Комиссия, €")}
            {field("walk_forward_folds", "Walk-forward (0=выкл)")}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <Button className="rounded-xl" onClick={run} disabled={busy}>
              {busy ? "Прогоняю историю…" : "Запустить бэктест"}
            </Button>
            <p className="text-[10px] text-muted-foreground">
              ИИ-факторы в бэктесте выключены (историчных векторов нет) —
              проверяется формульная часть стратегии с учётом спреда,
              проскальзывания и комиссии.
            </p>
          </div>
          {error && <p className="mt-2 text-xs text-[#ff3b30]">{error}</p>}
        </CardContent>
      </Card>

      {result && m && (
        <>
          <div className="grid grid-cols-6 gap-3">
            <Kpi label="Сделок" value={String(m.trades)} sub={`${m.wins}W / ${m.losses}L`} />
            <Kpi label="Win Rate" value={m.win_rate != null ? `${m.win_rate}%` : "—"} />
            <Kpi label="Profit Factor" value={m.profit_factor?.toFixed(2) ?? "—"}
                 sub={m.sharpe_per_trade != null ? `Sharpe ${m.sharpe_per_trade}` : undefined} />
            <Kpi label="Доходность" value={`${m.total_return_pct > 0 ? "+" : ""}${m.total_return_pct}%`}
                 tone={m.total_return_pct >= 0 ? "up" : "down"}
                 sub={fmtMoney2(m.final_equity)} />
            <Kpi label="Макс. просадка" value={`${m.max_drawdown_pct}%`} tone="down" />
            <Kpi label="Матожидание" value={m.expectancy_r != null ? `${m.expectancy_r}R` : "—"}
                 sub={m.expectancy_eur != null ? fmtMoney2(m.expectancy_eur) : undefined} />
          </div>

          <Card className="rounded-2xl border-black/5 shadow-sm">
            <CardContent className="pt-4">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold tracking-tight">
                  Кривая капитала · {pretty(result.instrument)} {result.timeframe}
                </h3>
                <Button size="sm" variant="outline" className="rounded-xl"
                        onClick={analyze} disabled={analyzing || !aiEnabled}>
                  {analyzing ? "Анализирую…" : "ИИ-анализ результатов"}
                </Button>
              </div>
              <EquityChart curve={result.equity_curve} height={200} />
              {analysis && (
                <p className="mt-3 whitespace-pre-wrap rounded-xl bg-black/[0.02] p-3 text-xs leading-relaxed">
                  {analysis}
                </p>
              )}
            </CardContent>
          </Card>

          {result.walk_forward?.folds && (
            <Card className="rounded-2xl border-black/5 shadow-sm">
              <CardContent className="pt-4">
                <h3 className="mb-2 text-sm font-semibold tracking-tight">
                  Walk-forward · OOS сделок: {result.walk_forward.oos_trades} ·
                  OOS P&L: {fmtMoney2(result.walk_forward.oos_pnl_eur ?? 0)}
                </h3>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Фолд</TableHead>
                      <TableHead className="text-right">Порог (train)</TableHead>
                      <TableHead className="text-right">PF train</TableHead>
                      <TableHead className="text-right">Сделок test</TableHead>
                      <TableHead className="text-right">WR test</TableHead>
                      <TableHead className="text-right">PF test</TableHead>
                      <TableHead className="text-right">Доходн. test</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.walk_forward.folds.map((f) => (
                      <TableRow key={f.fold}>
                        <TableCell className="text-xs">{f.fold}</TableCell>
                        <TableCell className="text-right text-xs tabular-nums">{f.optimized_min_score}</TableCell>
                        <TableCell className="text-right text-xs tabular-nums">{f.train_pf ?? "—"}</TableCell>
                        <TableCell className="text-right text-xs tabular-nums">{f.test.trades}</TableCell>
                        <TableCell className="text-right text-xs tabular-nums">{f.test.win_rate ?? "—"}%</TableCell>
                        <TableCell className="text-right text-xs tabular-nums">{f.test.profit_factor ?? "—"}</TableCell>
                        <TableCell className={`text-right text-xs tabular-nums ${
                          (f.test.total_return_pct ?? 0) >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                          {f.test.total_return_pct}%
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          <Card className="rounded-2xl border-black/5 shadow-sm">
            <CardContent className="pt-4">
              <h3 className="mb-2 text-sm font-semibold tracking-tight">
                Сделки ({result.trades.length} последних)
              </h3>
              <div className="max-h-[300px] overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Вход</TableHead>
                      <TableHead>Напр.</TableHead>
                      <TableHead className="text-right">Оценка</TableHead>
                      <TableHead className="text-right">Вход → Выход</TableHead>
                      <TableHead className="text-right">Баров</TableHead>
                      <TableHead>Итог</TableHead>
                      <TableHead className="text-right">R</TableHead>
                      <TableHead className="text-right">P&L, €</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {[...result.trades].reverse().map((t, i) => (
                      <TableRow key={i}>
                        <TableCell className="text-[11px] tabular-nums">
                          {new Date(t.entry_time * 1000).toLocaleString("ru-RU", {
                            day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                        </TableCell>
                        <TableCell className={`text-xs font-semibold ${
                          t.direction === "BUY" ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                          {t.direction}
                        </TableCell>
                        <TableCell className="text-right text-xs tabular-nums">{t.score}</TableCell>
                        <TableCell className="text-right text-xs tabular-nums">{t.entry} → {t.exit}</TableCell>
                        <TableCell className="text-right text-xs tabular-nums">{t.bars_held}</TableCell>
                        <TableCell className="text-[11px]">
                          {t.status === "hit_tp" ? "✅ TP" : t.status === "hit_sl" ? "🛑 SL" : "⏳ истёк"}
                        </TableCell>
                        <TableCell className={`text-right text-xs tabular-nums ${
                          t.r >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                          {t.r > 0 ? "+" : ""}{t.r}
                        </TableCell>
                        <TableCell className={`text-right text-xs tabular-nums ${
                          t.pnl_eur >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                          {fmtMoney2(t.pnl_eur)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {runs.length > 0 && (
        <Card className="rounded-2xl border-black/5 shadow-sm">
          <CardContent className="pt-4">
            <h3 className="mb-2 text-sm font-semibold tracking-tight">
              Прошлые прогоны — сравнение
            </h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Инструмент</TableHead>
                  <TableHead className="text-right">Сделок</TableHead>
                  <TableHead className="text-right">WR</TableHead>
                  <TableHead className="text-right">PF</TableHead>
                  <TableHead className="text-right">Доходн.</TableHead>
                  <TableHead className="text-right">Просадка</TableHead>
                  <TableHead>Когда</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.slice(0, 10).map((r) => (
                  <TableRow key={r.run_id}>
                    <TableCell className="text-xs text-muted-foreground">#{r.run_id}</TableCell>
                    <TableCell className="text-xs font-medium">
                      {pretty(r.instrument)} · {r.timeframe}
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{r.metrics.trades}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{r.metrics.win_rate ?? "—"}%</TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{r.metrics.profit_factor ?? "—"}</TableCell>
                    <TableCell className={`text-right text-xs tabular-nums ${
                      r.metrics.total_return_pct >= 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                      {r.metrics.total_return_pct}%
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">{r.metrics.max_drawdown_pct}%</TableCell>
                    <TableCell className="text-[11px] text-muted-foreground">
                      {r.created_at ? new Date(r.created_at).toLocaleString("ru-RU") : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Kpi({ label, value, sub, tone }: {
  label: string; value: string; sub?: string; tone?: "up" | "down";
}) {
  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardContent className="pt-4">
        <p className="text-[10px] text-muted-foreground">{label}</p>
        <p className={`text-base font-semibold tabular-nums tracking-tight ${
          tone === "up" ? "text-[#34c759]" : tone === "down" ? "text-[#ff3b30]" : ""}`}>
          {value}
        </p>
        {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}
