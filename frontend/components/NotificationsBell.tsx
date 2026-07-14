"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, type NotificationRow } from "@/lib/api";

export function NotificationsBell() {
  const [items, setItems] = useState<NotificationRow[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

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
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const markAll = async () => {
    await api.markNotificationsRead().catch(() => {});
    refresh();
  };

  return (
    <div className="relative" ref={boxRef}>
      <Button variant="ghost" size="sm" className="relative rounded-xl px-2"
              onClick={() => setOpen((o) => !o)}>
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#ff3b30] px-1 text-[9px] font-semibold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </Button>
      {open && (
        <div className="absolute right-0 top-10 z-50 w-[360px] rounded-2xl border border-black/5 bg-white p-2 shadow-xl">
          <div className="flex items-center justify-between px-2 py-1">
            <p className="text-sm font-semibold">Уведомления</p>
            {unread > 0 && (
              <button className="text-xs text-[#0a84ff]" onClick={markAll}>
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
                   className={`rounded-xl px-3 py-2 ${n.read ? "opacity-60" : "bg-[#0a84ff]/5"}`}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium">{n.title}</p>
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    {n.created_at ? new Date(n.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : ""}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-muted-foreground">{n.body}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
