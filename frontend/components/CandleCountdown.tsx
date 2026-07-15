"use client";

import { useEffect, useRef, useState } from "react";

const TF_SECONDS: Record<string, number> = {
  "1m": 60,
  "5m": 300,
  "15m": 900,
  "40m": 2400,
  "1h": 3600,
  "4h": 14400,
  "1d": 86400,
};

function fmt(total: number): string {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** Обратный отсчёт до закрытия текущей свечи (бары выровнены по UTC-эпохе,
 * как и у провайдеров данных). По нулю дёргает onExpire — график обновляется
 * сразу с новой свечой. */
export function CandleCountdown({ tf, onExpire }: {
  tf: string;
  onExpire?: () => void;
}) {
  const gran = TF_SECONDS[tf] ?? 3600;
  const [left, setLeft] = useState(() => gran - (Math.floor(Date.now() / 1000) % gran));
  const expireRef = useRef(onExpire);
  expireRef.current = onExpire;

  useEffect(() => {
    const tick = () => {
      const now = Math.floor(Date.now() / 1000);
      const remaining = gran - (now % gran);
      setLeft(remaining);
      if (remaining === gran) expireRef.current?.(); // свеча только что закрылась
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [gran]);

  const urgent = left <= (gran >= 3600 ? 60 : 10);
  return (
    <span
      className={`tabular-nums text-xs ${urgent ? "font-semibold text-[#ff9f0a]" : "text-muted-foreground"}`}
      title="До закрытия текущей свечи"
    >
      ⏱ {fmt(left)}
    </span>
  );
}
