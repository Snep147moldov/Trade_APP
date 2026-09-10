"use client";

import { useMemo, useState } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  ChevronRight,
  Plus,
  ShieldAlert,
  Wallet,
} from "lucide-react";

import { EquityChart } from "@/components/PriceChart";
import {
  fmtMoney2,
  fmtPct,
  pretty,
  type Settings,
  type SignalRow,
  type SignalStats,
} from "@/lib/api";

type Props = {
  stats: SignalStats | null;
  signals: SignalRow[];
  settings: Settings | null;
  username: string;
  /** переход в другой раздел — карточки на дашборде кликабельны */
  onGo: (view: string) => void;
  /** выбрать инструмент и открыть график */
  onPick: (instrument: string) => void;
};

const PERIODS = [
  { key: "today", label: "День" },
  { key: "week", label: "Неделя" },
  { key: "all", label: "Всё" },
] as const;
type Period = (typeof PERIODS)[number]["key"];

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Доброй ночи";
  if (h < 12) return "Доброе утро";
  if (h < 18) return "Добрый день";
  return "Добрый вечер";
}

/** Итог за период: у брокера он реальный, без брокера — по модели приложения.
 *  Смешивать нельзя: mt5_pnl и pnl_money расходились до смены знака. */
function periodPnl(stats: SignalStats | null, p: Period) {
  if (!stats) return { money: 0, closed: 0, real: false };
  const m = stats.mt5;
  if (p === "today") {
    return m.connected && m.today_real != null
      ? { money: m.today_real, closed: stats.today_closed, real: true }
      : { money: stats.today_money, closed: stats.today_closed, real: false };
  }
  if (p === "week") {
    return m.connected && m.week_real != null
      ? { money: m.week_real, closed: stats.week_closed, real: true }
      : { money: stats.week_money, closed: stats.week_closed, real: false };
  }
  return { money: stats.total_money, closed: stats.closed, real: false };
}

export function DashboardView({
  stats,
  signals,
  settings,
  username,
  onGo,
  onPick,
}: Props) {
  const [period, setPeriod] = useState<Period>("week");

  const balance = stats?.mt5.connected
    ? stats.mt5.balance ?? stats.current_equity
    : stats?.current_equity ?? settings?.account_equity ?? 0;
  const floating = stats?.mt5.floating ?? 0;
  const equity = stats?.mt5.equity ?? balance + floating;
  const pnl = periodPnl(stats, period);
  const pnlPct = balance > 0 ? (pnl.money / balance) * 100 : 0;

  // Выигрыши и потери за всё время — из закрытых сделок, деньгами брокера там,
  // где они есть. Именно это спрашивают в первую очередь: сколько заработал и
  // сколько потерял, а не сводный процент.
  const { won, lost, wonN, lostN } = useMemo(() => {
    let won = 0, lost = 0, wonN = 0, lostN = 0;
    for (const s of signals) {
      const v = s.mt5_pnl ?? s.pnl_money;
      if (v == null || s.status === "open") continue;
      if (v > 0) { won += v; wonN += 1; } else if (v < 0) { lost += v; lostN += 1; }
    }
    return { won, lost, wonN, lostN };
  }, [signals]);

  const openSignals = useMemo(
    () => signals.filter((s) => s.status === "open"),
    [signals],
  );
  const recent = useMemo(
    () =>
      signals
        .filter((s) => s.status !== "open" && (s.mt5_pnl ?? s.pnl_money) != null)
        .slice(0, 20),
    [signals],
  );

  const riskLimit = settings?.max_open_risk_pct ?? 0;
  const riskUsed = stats?.open_risk ?? 0;
  const riskPct = balance > 0 ? (riskUsed / balance) * 100 : 0;
  const riskFull = riskLimit > 0 ? Math.min(100, (riskPct / riskLimit) * 100) : 0;

  const curve = stats?.equity_curve ?? [];

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {/* ───────────────────────── герой: баланс и период ───────────────── */}
      <section className="shrink-0 rounded-3xl bg-card p-4 shadow-card sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground lg:hidden">
              {greeting()}, {username}
            </p>
            <p className="hidden text-[11px] font-medium uppercase tracking-wide text-muted-foreground lg:block">
              Баланс счёта
            </p>
          </div>
          <div className="flex shrink-0 rounded-full bg-muted p-0.5">
            {PERIODS.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => setPeriod(p.key)}
                className={`rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                  period === p.key
                    ? "bg-card font-medium text-foreground shadow-sm"
                    : "text-muted-foreground"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-1 flex flex-wrap items-end gap-x-4 gap-y-1">
          <p className="text-[34px] font-semibold leading-none tracking-tight tabular-nums sm:text-[44px] lg:text-[56px]">
            {fmtMoney2(balance)}
          </p>
          <div className="mb-1 flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium tabular-nums ${
                pnl.money >= 0 ? "bg-pos/10 text-pos" : "bg-neg/10 text-neg"
              }`}
            >
              {pnl.money >= 0 ? (
                <ArrowUpRight className="h-3 w-3" />
              ) : (
                <ArrowDownLeft className="h-3 w-3" />
              )}
              {fmtMoney2(pnl.money)}
            </span>
            <span className="text-xs text-muted-foreground tabular-nums">
              {fmtPct(pnlPct)} · {pnl.closed} сд.
              {!pnl.real && stats?.mt5.connected && " · расчёт"}
            </span>
          </div>
        </div>

        {floating !== 0 && (
          <p className="mt-1 text-xs text-muted-foreground tabular-nums">
            С учётом открытых:{" "}
            <span className={floating >= 0 ? "text-pos" : "text-neg"}>
              {fmtMoney2(equity)}
            </span>{" "}
            ({fmtMoney2(floating)} плавающий)
          </p>
        )}

        {/* кривая капитала — фон под числом, как в банковских приложениях */}
        {curve.length > 1 && (
          <div className="-mx-1 mt-2 hidden sm:block">
            <EquityChart curve={curve} height={120} />
          </div>
        )}
      </section>

      {/* ───────────────────────── быстрые действия (телефон) ────────────── */}
      <div className="flex shrink-0 items-center gap-2 lg:hidden">
        <button
          type="button"
          onClick={() => onGo("chart")}
          className="flex h-11 flex-1 items-center justify-center gap-2 rounded-2xl bg-card text-sm font-medium shadow-card"
        >
          <ArrowUpRight className="h-4 w-4" /> Сигнал
        </button>
        <button
          type="button"
          onClick={() => onGo("screener")}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand text-white shadow-card"
          aria-label="Найти инструмент"
        >
          <Plus className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={() => onGo("trades")}
          className="flex h-11 flex-1 items-center justify-center gap-2 rounded-2xl bg-card text-sm font-medium shadow-card"
        >
          <Wallet className="h-4 w-4" /> Сделки
        </button>
      </div>

      {/* ───────────────────────── показатели ───────────────────────────── */}
      <div className="grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="Заработано"
          value={fmtMoney2(won)}
          hint={`${wonN} прибыльных`}
          tone="pos"
          onClick={() => onGo("trades")}
        />
        <Tile
          label="Потеряно"
          value={fmtMoney2(lost)}
          hint={`${lostN} убыточных`}
          tone="neg"
          onClick={() => onGo("trades")}
        />
        <Tile
          label="Винрейт"
          value={stats?.win_rate != null ? `${stats.win_rate.toFixed(1)}%` : "—"}
          hint={`${stats?.wins ?? 0} из ${stats?.closed ?? 0}`}
          onClick={() => onGo("journal")}
        />
        <Tile
          label="Открытый риск"
          value={`${riskPct.toFixed(1)}%`}
          hint={riskLimit > 0 ? `лимит ${riskLimit.toFixed(0)}%` : "лимит не задан"}
          tone={riskFull >= 100 ? "neg" : riskFull >= 80 ? "warn" : undefined}
          bar={riskFull}
          onClick={() => onGo("risk")}
        />
      </div>

      {/* ───────────────────────── списки ──────────────────────────────── */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-2">
        <Panel
          title="Открытые позиции"
          count={openSignals.length}
          action={openSignals.length ? "Риск" : undefined}
          onAction={() => onGo("risk")}
          empty="Сейчас открытых позиций нет"
        >
          {openSignals.map((s) => (
            <Row
              key={s.id}
              left={pretty(s.instrument)}
              sub={`${s.timeframe} · ${s.direction === "BUY" ? "покупка" : "продажа"}${
                s.mt5_orders > 0 ? "" : " · без ордера"
              }`}
              right={
                s.mt5_pnl != null ? fmtMoney2(s.mt5_pnl) : `риск ${fmtMoney2(s.risk_amount)}`
              }
              tone={s.mt5_pnl != null ? (s.mt5_pnl >= 0 ? "pos" : "neg") : undefined}
              onClick={() => onPick(s.instrument)}
            />
          ))}
        </Panel>

        <Panel
          title="Последние сделки"
          count={recent.length}
          action="Все"
          onAction={() => onGo("trades")}
          empty="Закрытых сделок пока нет"
        >
          {recent.map((s) => {
            const v = s.mt5_pnl ?? s.pnl_money ?? 0;
            return (
              <Row
                key={s.id}
                left={pretty(s.instrument)}
                sub={`${s.timeframe} · ${
                  s.status === "hit_tp"
                    ? "цель"
                    : s.status === "hit_sl"
                      ? "стоп"
                      : "по сроку"
                }`}
                right={fmtMoney2(v)}
                tone={v >= 0 ? "pos" : "neg"}
                onClick={() => onPick(s.instrument)}
              />
            );
          })}
        </Panel>
      </div>
    </div>
  );
}

function Tile({
  label,
  value,
  hint,
  tone,
  bar,
  onClick,
}: {
  label: string;
  value: string;
  hint: string;
  tone?: "pos" | "neg" | "warn";
  bar?: number;
  onClick: () => void;
}) {
  const color =
    tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : tone === "warn" ? "text-warn" : "";
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-2xl bg-card p-3 text-left shadow-card transition-shadow hover:shadow-pop sm:p-4"
    >
      <p className="truncate text-[11px] text-muted-foreground">{label}</p>
      <p className={`mt-0.5 text-lg font-semibold tabular-nums sm:text-xl ${color}`}>
        {value}
      </p>
      {bar != null ? (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full ${
              tone === "neg" ? "bg-neg" : tone === "warn" ? "bg-warn" : "bg-brand"
            }`}
            style={{ width: `${Math.max(2, bar)}%` }}
          />
        </div>
      ) : (
        <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{hint}</p>
      )}
      {bar != null && (
        <p className="mt-1 truncate text-[11px] text-muted-foreground">{hint}</p>
      )}
    </button>
  );
}

function Panel({
  title,
  count,
  action,
  onAction,
  empty,
  children,
}: {
  title: string;
  count: number;
  action?: string;
  onAction?: () => void;
  empty: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex min-h-0 flex-col rounded-3xl bg-card shadow-card">
      <div className="flex shrink-0 items-center justify-between px-4 pb-2 pt-3.5">
        <h3 className="text-sm font-semibold tracking-tight">
          {title}
          {count > 0 && (
            <span className="ml-2 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground">
              {count}
            </span>
          )}
        </h3>
        {action && (
          <button
            type="button"
            onClick={onAction}
            className="inline-flex items-center gap-0.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            {action} <ChevronRight className="h-3 w-3" />
          </button>
        )}
      </div>
      {/* список прокручивается внутри — страница целиком не прокручивается */}
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {count === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-muted-foreground">{empty}</p>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

function Row({
  left,
  sub,
  right,
  tone,
  onClick,
}: {
  left: string;
  sub: string;
  right: string;
  tone?: "pos" | "neg";
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-2xl px-2 py-2 text-left transition-colors hover:bg-accent"
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
        {tone === "neg" ? (
          <ArrowDownLeft className="h-4 w-4 text-neg" />
        ) : tone === "pos" ? (
          <ArrowUpRight className="h-4 w-4 text-pos" />
        ) : (
          <ShieldAlert className="h-4 w-4 text-muted-foreground" />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium">{left}</span>
        <span className="block truncate text-[11px] text-muted-foreground">{sub}</span>
      </span>
      <span
        className={`shrink-0 text-[13px] font-medium tabular-nums ${
          tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-muted-foreground"
        }`}
      >
        {right}
      </span>
    </button>
  );
}
