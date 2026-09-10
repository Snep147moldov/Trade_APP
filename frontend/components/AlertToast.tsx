"use client";

import { useEffect, useState } from "react";
import { CircleCheck, CircleX, TriangleAlert, X } from "lucide-react";

import type { CalendarEvent } from "@/lib/api";

/** Предупреждения о новостях всплывают карточкой и закрываются.
 *
 *  Раньше это была полоса поверх страницы: она занимала строку постоянно,
 *  сдвигала весь макет вниз и её нельзя было убрать — а важная новость висит
 *  в календаре часами. Закрытые запоминаются по времени и заголовку, чтобы
 *  не возвращались на следующем обновлении календаря. */
export function AlertToast({ alerts }: { alerts: CalendarEvent[] }) {
  const [hidden, setHidden] = useState<string[]>([]);
  const key = (a: CalendarEvent) => `${a.time}-${a.title}`;
  const shown = alerts.filter((a) => !hidden.includes(key(a)));
  if (shown.length === 0) return null;

  return (
    <div className="pointer-events-none fixed right-3 top-16 z-30 flex w-[min(22rem,calc(100vw-1.5rem))] flex-col gap-2 sm:right-5">
      {shown.slice(0, 3).map((a, i) => {
        const mins = Math.max(1, Math.round((a.time * 1000 - Date.now()) / 60000));
        return (
          <div
            key={key(a)}
            style={{ animationDelay: `${i * 90}ms` }}
            className="drop pointer-events-auto relative flex items-start gap-2.5 overflow-hidden rounded-2xl bg-brand/92 p-3 pl-4 text-white shadow-pop backdrop-blur-xl"
          >
            {/* цветной корешок слева: на стеклянной карточке одна иконка
                терялась среди остального стекла */}
            <span className="absolute inset-y-0 left-0 w-1 bg-white/70" />
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white/20 text-white">
              <TriangleAlert className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium">
                Через {mins} мин · {a.currency}
              </p>
              <p className="mt-0.5 line-clamp-2 text-[11px] text-white/80">{a.title}</p>
            </div>
            <button
              type="button"
              onClick={() => setHidden((v) => [...v, key(a)])}
              aria-label="Скрыть"
              className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-white/70 transition-all hover:bg-white/15 hover:text-white active:scale-90"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
      {shown.length > 3 && (
        <button
          type="button"
          onClick={() => setHidden(alerts.map(key))}
          className="glass pointer-events-auto rounded-xl px-3 py-1.5 text-[11px] text-muted-foreground transition-all hover:text-foreground"
        >
          Скрыть все ({shown.length})
        </button>
      )}
    </div>
  );
}


/** Отклик на действие: нажатие на «новый сигнал» ничего не показывало, потому
 *  что результат рисовался только внутри карточки сигнала — а её на дашборде
 *  нет. Теперь ответ виден с любого экрана и сам гаснет. */
export function FlashToast({
  message,
  onClose,
}: {
  message: string | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 9000);
    return () => clearTimeout(t);
  }, [message, onClose]);

  if (!message) return null;
  const bad = /не сохранён|не удалось|ошибка/i.test(message);

  return (
    <div className="pointer-events-none fixed inset-x-3 bottom-24 z-40 flex justify-center sm:inset-x-auto sm:bottom-6 sm:left-1/2 sm:-translate-x-1/2">
      <div
        className={`glass-strong rise pointer-events-auto flex max-w-[34rem] items-start gap-2.5 rounded-2xl p-3 pl-4 shadow-pop ring-1 ${
          bad ? "ring-neg/30" : "ring-pos/30"
        }`}
      >
        <span className={`absolute inset-y-0 left-0 w-1 rounded-l-2xl ${bad ? "bg-neg" : "bg-pos"}`} />
        {bad ? (
          <CircleX className="mt-0.5 h-4 w-4 shrink-0 text-neg" />
        ) : (
          <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-pos" />
        )}
        <p className="min-w-0 flex-1 text-[12px] leading-relaxed">{message}</p>
        <button
          type="button"
          onClick={onClose}
          aria-label="Закрыть"
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-all hover:bg-accent hover:text-foreground active:scale-90"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
