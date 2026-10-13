"use client";

import { useEffect, useState } from "react";
import { CalendarClock, Check, CreditCard, Minus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { api, type PaymentRow, type PlanSummary, type SubscriptionView } from "@/lib/api";
import { tr } from "@/lib/i18n";

/** Подписи состояний. Ключ — то, что отдаёт сервер. */
const STATUS_LABEL: Record<string, string> = {
  trialing: "Пробный период",
  active: "Активна",
  past_due: "Оплата просрочена",
  suspended: "Приостановлена",
  cancelled: "Отменена",
  expired: "Истекла",
};

/** Права в том порядке, в каком их читает человек: сначала что можно делать,
 *  потом сколько. */
const RIGHTS_ORDER = [
  "max_instruments",
  "timeframes",
  "max_open_signals",
  "autotrade",
  "mt5",
  "backtest",
  "ai_per_day",
  "history_days",
  "telegram",
  "api_access",
  "support",
];

const RIGHT_LABEL: Record<string, string> = {
  max_instruments: "Инструментов в «Избранном»",
  timeframes: "Таймфреймы",
  max_open_signals: "Открытых сигналов",
  autotrade: "Автоторговля",
  mt5: "Подключение MT5",
  backtest: "Бэктест",
  ai_per_day: "ИИ-анализов в сутки",
  history_days: "Глубина истории, дней",
  telegram: "Telegram",
  api_access: "Доступ к API",
  support: "Поддержка",
};

/** Человеческое значение права: `-1` — без предела, логическое — да/нет. */
function rightValue(value: unknown): string {
  if (typeof value === "boolean") return value ? tr("да") : tr("нет");
  if (typeof value === "number") return value < 0 ? tr("без предела") : String(value);
  if (Array.isArray(value)) return value.join(", ");
  return String(value ?? "—");
}

/**
 * Подписка в настройках: тариф, срок, что он включает и история оплат.
 *
 * Отдельная карточка, а не строка в «Состоянии»: это единственное место, где
 * человек видит, до какого числа он оплачен, и единственное, которое
 * открывается по требованию из напоминания об оплате.
 */
export function SubscriptionCard({ trigger }: { trigger: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<SubscriptionView | null>(null);
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [payments, setPayments] = useState<PaymentRow[]>([]);

  // напоминание об оплате открывает именно этот раздел
  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener("fxnav-open-billing", onOpen);
    return () => window.removeEventListener("fxnav-open-billing", onOpen);
  }, []);

  useEffect(() => {
    if (!open) return;
    api.mySubscription().then(setView).catch(() => setView(null));
    api.plans().then(setPlans).catch(() => setPlans([]));
    api.myPayments().then(setPayments).catch(() => setPayments([]));
  }, [open]);

  const left = view?.days_left ?? null;
  const until = view?.current_period_end
    ? new Date(view.current_period_end).toLocaleDateString()
    : "—";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="tracking-tight">{tr("Подписка")}</DialogTitle>
        </DialogHeader>

        {!view ? (
          <p className="text-sm text-muted-foreground">{tr("Загружаю")}…</p>
        ) : (
          <div className="space-y-5">
            <div className="glass rounded-2xl p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <p className="text-lg font-semibold tracking-tight">
                    {view.plan?.name ?? tr("Без тарифа")}
                  </p>
                  <p className="text-xs text-muted-foreground">{view.plan?.description ?? ""}</p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                    view.active ? "bg-pos/10 text-pos" : "bg-neg/10 text-neg"
                  }`}
                >
                  {tr(STATUS_LABEL[view.status] ?? view.status)}
                </span>
              </div>

              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:text-[13px]">
                <Row label={tr("Оплачено до")} value={until} />
                <Row
                  label={tr("Осталось")}
                  value={
                    left === null
                      ? "—"
                      : left >= 0
                        ? tr("{0} дн.", left)
                        : tr("просрочено на {0} дн.", Math.abs(left))
                  }
                />
                <Row
                  label={tr("Стоимость")}
                  value={
                    view.plan
                      ? `${(view.plan.price_cents / 100).toFixed(2)} ${view.plan.currency} / ${view.plan.period_days} ${tr("дн.")}`
                      : "—"
                  }
                />
                <Row
                  label={tr("Льготных дней после оплаты")}
                  value={String(view.grace_days)}
                />
              </dl>

              {!view.active && (
                <Button className="mt-4 w-full rounded-xl">
                  <CreditCard className="mr-2 h-4 w-4" />
                  {tr("Оплатить подписку")}
                </Button>
              )}
            </div>

            <section>
              <h3 className="mb-2 text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
                {tr("Что включено")}
              </h3>
              <dl className="glass space-y-1.5 rounded-2xl p-3 text-sm sm:text-[13px]">
                {RIGHTS_ORDER.filter((key) => key in view.entitlements).map((key) => (
                  <div key={key} className="flex items-center justify-between gap-3">
                    <dt className="text-muted-foreground">{tr(RIGHT_LABEL[key] ?? key)}</dt>
                    <dd className="flex items-center gap-1.5 tabular-nums">
                      {typeof view.entitlements[key] === "boolean" &&
                        (view.entitlements[key] ? (
                          <Check className="h-3.5 w-3.5 text-pos" />
                        ) : (
                          <Minus className="h-3.5 w-3.5 text-muted-foreground" />
                        ))}
                      {rightValue(view.entitlements[key])}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>

            {plans.length > 0 && (
              <section>
                <h3 className="mb-2 text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
                  {tr("Тарифы")}
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {plans.map((plan) => (
                    <div
                      key={plan.code}
                      className={`glass rounded-2xl p-3 ${
                        plan.code === view.plan?.code ? "ring-1 ring-brand/40" : ""
                      }`}
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-medium">{plan.name}</span>
                        <span className="text-sm tabular-nums">
                          {(plan.price_cents / 100).toFixed(0)} {plan.currency}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-muted-foreground">{plan.description}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section>
              <h3 className="mb-2 text-[13px] font-medium uppercase tracking-wide text-muted-foreground">
                {tr("История оплат")}
              </h3>
              {payments.length === 0 ? (
                <p className="text-xs text-muted-foreground">{tr("Оплат пока не было.")}</p>
              ) : (
                <ul className="glass divide-y rounded-2xl text-sm sm:text-[13px]">
                  {payments.map((p) => (
                    <li key={p.id} className="flex items-center justify-between gap-3 px-3 py-2">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <CalendarClock className="h-3.5 w-3.5 shrink-0" />
                        {p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">{p.invoice_no}</span>
                      <span className="tabular-nums">
                        {(p.amount_cents / 100).toFixed(2)} {p.currency}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}
