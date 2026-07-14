"use client";

import { useEffect, useState } from "react";
import type { MarketState } from "@/lib/api";
import { api } from "@/lib/api";

export function MarketClock() {
  const [market, setMarket] = useState<MarketState | null>(null);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const load = () => api.market().then(setMarket).catch(() => {});
    load();
    const marketId = setInterval(load, 60_000);
    const clockId = setInterval(() => setNow(new Date()), 1000);
    return () => {
      clearInterval(marketId);
      clearInterval(clockId);
    };
  }, []);

  if (!market) return null;

  const local = now.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const utc = now.toLocaleTimeString("ru-RU", {
    hour: "2-digit", minute: "2-digit", timeZone: "UTC",
  });

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5">
        <span
          className={`inline-block h-2 w-2 rounded-full ${
            market.is_open ? "bg-[#34c759]" : "bg-[#ff3b30]"
          }`}
        />
        <span className="text-xs font-medium">
          {market.is_open ? "Рынок открыт" : "Рынок закрыт"}
        </span>
      </div>
      <div className="hidden items-center gap-1 lg:flex">
        {market.sessions.map((s) => (
          <span
            key={s.name}
            title={`${s.name}: ${s.open_utc}–${s.close_utc} UTC`}
            className={`rounded-full px-2 py-0.5 text-[10px] ${
              s.active
                ? "bg-[#34c759]/10 font-medium text-[#34c759]"
                : "bg-muted text-muted-foreground/60"
            }`}
          >
            {s.name}
          </span>
        ))}
      </div>
      <span className="text-xs tabular-nums text-muted-foreground" suppressHydrationWarning>
        {local} <span className="text-muted-foreground/50">· UTC {utc}</span>
      </span>
    </div>
  );
}
