"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarClock, CreditCard, Lock, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, type SubscriptionView } from "@/lib/api";
import { tr } from "@/lib/i18n";

/** Как часто перечитываем состояние подписки (мс). Период кончается по
 *  календарю, не по действию пользователя, поэтому экран обязан узнать об
 *  этом сам, а не при следующей перезагрузке. */
const POLL_MS = 5 * 60 * 1000;

/** Ключ, под которым запоминается закрытое напоминание. */
const DISMISS_KEY = "fxnav-billing-dismissed";

/**
 * Напоминания об оплате и блокировка, когда она просрочена.
 *
 * Три уровня, намеренно разные по настойчивости:
 *
 * - `due_soon` — тонкая полоса сверху. Закрывается и не возвращается в тот же
 *   день: человек уже увидел, повторять в каждой вкладке незачем.
 * - `due` / `past_due` — заметная полоса, которая закрывается только до
 *   следующего дня. Доступ ещё есть, но молчать об этом нельзя.
 * - `blocked` — экран поверх всего, без кнопки закрытия. Историю под ним
 *   видно: человек за неё заплатил. Создавать новое и торговать нельзя, и
 *   это решает сервер — здесь только объяснение.
 */
export function SubscriptionGate({ children }: { children: React.ReactNode }) {
  const [view, setView] = useState<SubscriptionView | null>(null);
  const [dismissedFor, setDismissedFor] = useState<string | null>(null);

  useEffect(() => {
    try {
      setDismissedFor(localStorage.getItem(DISMISS_KEY));
    } catch {
      // приватное окно: напоминание просто будет показываться каждый раз
    }
  }, []);

  const load = useCallback(() => {
    api
      .mySubscription()
      .then(setView)
      .catch(() => setView(null));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [load]);

  const dismiss = () => {
    const today = new Date().toISOString().slice(0, 10);
    setDismissedFor(today);
    try {
      localStorage.setItem(DISMISS_KEY, today);
    } catch {}
  };

  // Пока состояние неизвестно — ничего не решаем: мигнувший блок на
  // медленной сети пугает сильнее, чем отсутствие предупреждения на секунду.
  if (!view) return <>{children}</>;

  if (view.notice === "blocked") {
    return (
      <>
        <div className="pointer-events-none select-none opacity-40 blur-[2px]">{children}</div>
        <BlockedScreen view={view} />
      </>
    );
  }

  const today = new Date().toISOString().slice(0, 10);
  const hidden = view.notice === "due_soon" && dismissedFor === today;

  return (
    <>
      {view.notice !== "none" && !hidden && <Banner view={view} onDismiss={dismiss} />}
      {children}
    </>
  );
}

/** Строка напоминания над приложением. */
function Banner({ view, onDismiss }: { view: SubscriptionView; onDismiss: () => void }) {
  const left = view.days_left ?? 0;
  const urgent = view.notice !== "due_soon";

  const text =
    view.notice === "due_soon"
      ? tr("Подписка заканчивается через {0} дн. Продлите, чтобы ничего не прервалось.", left)
      : view.notice === "due"
        ? tr("Срок подписки истёк сегодня. Продлите, чтобы сохранить доступ.")
        : tr("Оплата не прошла. Доступ сохраняется ещё {0} дн., потом будет приостановлен.", Math.max(0, view.grace_days + left));

  return (
    <div
      role="status"
      className={`flex items-center gap-3 px-4 py-2 text-[13px] sm:text-xs ${
        urgent ? "bg-neg/10 text-neg" : "bg-warn/10 text-warn"
      }`}
    >
      <CalendarClock className="h-4 w-4 shrink-0" />
      <span className="min-w-0 flex-1">{text}</span>
      <Button size="sm" className="h-7 rounded-lg px-3 text-xs" onClick={() => goToBilling()}>
        {tr("Продлить")}
      </Button>
      <button
        type="button"
        onClick={onDismiss}
        aria-label={tr("Скрыть")}
        className="rounded p-1 opacity-70 transition-opacity hover:opacity-100"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/** Экран, который не закрывается. */
function BlockedScreen({ view }: { view: SubscriptionView }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center overflow-y-auto bg-background/80 px-4 py-10 backdrop-blur-sm">
      <div className="glass w-full max-w-md rounded-3xl p-6 text-center shadow-pop">
        <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-neg/10 text-neg">
          <Lock className="h-6 w-6" />
        </span>
        <h2 className="text-lg font-semibold tracking-tight">
          {view.status === "cancelled" ? tr("Подписка отменена") : tr("Подписка не оплачена")}
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {tr("Новые сигналы не создаются и сделки не открываются. История остаётся доступной — вы за неё заплатили.")}
        </p>
        {view.plan && (
          <p className="mt-3 text-xs text-muted-foreground">
            {tr("Тариф: {0} · {1} {2} за {3} дн.", view.plan.name, (view.plan.price_cents / 100).toFixed(2), view.plan.currency, view.plan.period_days)}
          </p>
        )}
        <div className="mt-5 flex flex-col gap-2">
          <Button className="w-full rounded-xl" onClick={() => goToBilling()}>
            <CreditCard className="mr-2 h-4 w-4" />
            {tr("Оплатить подписку")}
          </Button>
          <Button
            variant="outline"
            className="w-full rounded-xl"
            onClick={() => {
              window.dispatchEvent(new Event("cnx-unauthorized"));
            }}
          >
            {tr("Выйти")}
          </Button>
        </div>
        <p className="mt-4 text-[11px] text-muted-foreground">
          {tr("Если вы уже оплатили, напишите администратору — он отметит оплату вручную.")}
        </p>
      </div>
    </div>
  );
}

/** Открыть раздел подписки в настройках. */
function goToBilling(): void {
  window.dispatchEvent(new CustomEvent("fxnav-open-billing"));
}
