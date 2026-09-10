"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, type NotificationRow } from "@/lib/api";

export function NotificationsBell({ onPick }: {
  onPick?: (instrument: string) => void;
}) {
  const [items, setItems] = useState<NotificationRow[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  // Панель рисуется порталом с фиксированной позицией: полоса действий в шапке
  // прокручивается по горизонтали, а overflow-x обрезает всё, что выходит за
  // её границы — выпадающий список просто не было видно.
  const [pos, setPos] = useState<{ top: number; right: number } | null>(null);

  const openItem = async (n: NotificationRow) => {
    if (!n.read) {
      await api.markNotificationsRead([n.id]).catch(() => {});
      refresh();
    }
    if (n.instrument && onPick) {
      onPick(n.instrument);
      setOpen(false);
    }
  };

  const refresh = useCallback(async () => {
    try {
      const d = await api.notifications();
      setItems(d.notifications);
      setUnread(d.unread);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (!open) return;
    const place = () => {
      const r = btnRef.current?.getBoundingClientRect();
      if (r) {
        setPos({
          top: r.bottom + 8,
          right: Math.max(8, window.innerWidth - r.right),
        });
      }
    };
    place();
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (
        boxRef.current && !boxRef.current.contains(t) &&
        !document.getElementById("cnx-notifications")?.contains(t)
      ) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", place);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", place);
    };
  }, [open]);

  const markAll = async () => {
    await api.markNotificationsRead().catch(() => {});
    refresh();
  };

  return (
    <div className="relative" ref={boxRef}>
      <Button ref={btnRef} variant="ghost" size="sm" className="relative rounded-xl px-2"
              onClick={() => setOpen((o) => !o)}>
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-neg px-1 text-[11px] sm:text-[9px] font-semibold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </Button>
      {open && pos && createPortal(
        <div
          id="cnx-notifications"
          style={{ top: pos.top, right: pos.right }}
          className="glass-strong drop fixed z-50 w-[min(22rem,calc(100vw-1rem))] rounded-2xl p-2 shadow-pop"
        >
          <div className="flex items-center justify-between px-2 py-1">
            <p className="text-sm font-semibold">Уведомления</p>
            {unread > 0 && (
              <button className="text-xs text-brand-ink" onClick={markAll}>
                Прочитать все
              </button>
            )}
          </div>
          <div className="max-h-[380px] space-y-1 overflow-y-auto">
            {items.length === 0 && (
              <p className="px-2 py-6 text-center text-xs text-muted-foreground">
                Пока пусто. Алерты, риск-события и календарь появятся здесь.
              </p>
            )}
            {items.map((n) => (
              <div key={n.id}
                   onClick={() => openItem(n)}
                   className={`rounded-xl px-3 py-2 ${n.read ? "opacity-60" : "bg-brand/5"} ${
                     n.instrument && onPick ? "cursor-pointer hover:bg-brand/10" : ""}`}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium">{n.title}</p>
                  <span className="shrink-0 text-xs sm:text-[10px] text-muted-foreground">
                    {n.created_at ? new Date(n.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : ""}
                  </span>
                </div>
                <p className="mt-0.5 text-[13px] sm:text-[11px] text-muted-foreground">{n.body}</p>
                {n.instrument && onPick && (
                  <p className="mt-0.5 text-xs sm:text-[10px] font-medium text-brand-ink">
                    Открыть график →
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}
