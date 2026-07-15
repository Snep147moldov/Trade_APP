"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { api, pretty, type AlertRow } from "@/lib/api";

const KIND_LABELS: Record<string, string> = {
  price_above: "Цена выше уровня",
  price_below: "Цена ниже уровня",
  pct_move: "Движение на N%",
  rsi_above: "RSI выше",
  rsi_below: "RSI ниже",
  macd_cross: "MACD кросс",
  ma_cross: "Кросс EMA",
  bb_breakout: "Пробой Боллинджера",
  atr_spike: "Всплеск волатильности",
  volume_spike: "Всплеск объёма",
  ai_signal: "ИИ-сигнал (|оценка| ≥ порога)",
};

// which numeric params each kind needs
const KIND_PARAMS: Record<string, { key: string; label: string; def: string }[]> = {
  price_above: [{ key: "level", label: "Уровень", def: "" }],
  price_below: [{ key: "level", label: "Уровень", def: "" }],
  pct_move: [
    { key: "pct", label: "%", def: "1" },
    { key: "bars", label: "Баров", def: "12" },
  ],
  rsi_above: [{ key: "level", label: "RSI", def: "70" }],
  rsi_below: [{ key: "level", label: "RSI", def: "30" }],
  macd_cross: [],
  ma_cross: [
    { key: "fast", label: "Быстрая EMA", def: "20" },
    { key: "slow", label: "Медленная EMA", def: "50" },
  ],
  bb_breakout: [],
  atr_spike: [{ key: "mult", label: "× среднего ATR", def: "1.8" }],
  volume_spike: [{ key: "mult", label: "× среднего объёма", def: "2.5" }],
  ai_signal: [{ key: "min_score", label: "Мин. |оценка|", def: "0.3" }],
};

const TFS = ["1m", "5m", "15m", "40m", "1h", "4h", "1d"];

export function AlertsDialog({ watchlist, instrument }: {
  watchlist: string[];
  instrument: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [kind, setKind] = useState("price_above");
  const [symbol, setSymbol] = useState("");
  const [tf, setTf] = useState("1h");
  const [direction, setDirection] = useState<"bull" | "bear">("bull");
  const [params, setParams] = useState<Record<string, string>>({});
  const [channels, setChannels] = useState({ app: true, telegram: false, email: false });
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setAlerts((await api.alerts()).alerts);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (open) {
      refresh();
      setSymbol((s) => s || instrument || watchlist[0] || "");
    }
  }, [open, refresh, instrument, watchlist]);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const p: Record<string, unknown> = {};
      for (const f of KIND_PARAMS[kind] ?? []) {
        const v = parseFloat(params[f.key] ?? f.def);
        if (!Number.isNaN(v)) p[f.key] = v;
      }
      if (kind === "macd_cross" || kind === "ma_cross") p.direction = direction;
      await api.createAlert({
        instrument: symbol.toUpperCase().replace("/", "_"),
        timeframe: tf,
        kind,
        params: p,
        channels: Object.entries(channels).filter(([, v]) => v).map(([k]) => k),
        note,
      });
      setNote("");
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message.slice(0, 140) : "не удалось создать");
    }
    setBusy(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="rounded-xl">Алерты</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto rounded-2xl sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle className="tracking-tight">Кастомные алерты</DialogTitle>
          <DialogDescription>
            Цена, индикаторы, волатильность, объём, ИИ-сигналы. Проверка раз в
            минуту; доставка: приложение / Telegram / e-mail.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 rounded-2xl bg-black/[0.02] p-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Инструмент</Label>
              <Input className="rounded-xl" value={symbol} placeholder="EUR_USD"
                     onChange={(e) => setSymbol(e.target.value)} list="alert-symbols" />
              <datalist id="alert-symbols">
                {watchlist.map((w) => <option key={w} value={w} />)}
              </datalist>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Тип</Label>
              <select className="h-9 w-full rounded-xl border bg-transparent px-2 text-sm"
                      value={kind} onChange={(e) => { setKind(e.target.value); setParams({}); }}>
                {Object.entries(KIND_LABELS).map(([k, l]) => (
                  <option key={k} value={k}>{l}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Таймфрейм</Label>
              <select className="h-9 w-full rounded-xl border bg-transparent px-2 text-sm"
                      value={tf} onChange={(e) => setTf(e.target.value)}>
                {TFS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-3">
            {(KIND_PARAMS[kind] ?? []).map((f) => (
              <div key={f.key} className="space-y-1">
                <Label className="text-xs">{f.label}</Label>
                <Input className="rounded-xl" type="number" step="any"
                       value={params[f.key] ?? f.def}
                       onChange={(e) => setParams((p) => ({ ...p, [f.key]: e.target.value }))} />
              </div>
            ))}
            {(kind === "macd_cross" || kind === "ma_cross") && (
              <div className="space-y-1">
                <Label className="text-xs">Направление</Label>
                <select className="h-9 w-full rounded-xl border bg-transparent px-2 text-sm"
                        value={direction} onChange={(e) => setDirection(e.target.value as "bull" | "bear")}>
                  <option value="bull">Бычий</option>
                  <option value="bear">Медвежий</option>
                </select>
              </div>
            )}
            <div className="col-span-2 space-y-1">
              <Label className="text-xs">Заметка</Label>
              <Input className="rounded-xl" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs">
            {(["app", "telegram", "email"] as const).map((c) => (
              <label key={c} className="flex items-center gap-1.5">
                <Switch checked={channels[c]}
                        onCheckedChange={(v) => setChannels((ch) => ({ ...ch, [c]: v }))} />
                {c === "app" ? "Приложение" : c === "telegram" ? "Telegram" : "E-mail"}
              </label>
            ))}
            <Button size="sm" className="ml-auto rounded-xl" onClick={create}
                    disabled={busy || !symbol}>
              {busy ? "Создаю…" : "Создать алерт"}
            </Button>
          </div>
          {error && <p className="text-xs text-[#ff3b30]">{error}</p>}
        </div>

        <div className="space-y-1.5">
          {alerts.length === 0 && (
            <p className="py-3 text-center text-xs text-muted-foreground">Алертов пока нет.</p>
          )}
          {alerts.map((a) => (
            <div key={a.id} className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 shadow-sm">
              <Switch checked={a.active}
                      onCheckedChange={async (v) => {
                        await api.patchAlert(a.id, { active: v }).catch(() => {});
                        refresh();
                      }} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium">
                  {pretty(a.instrument)} · {a.timeframe} · {KIND_LABELS[a.kind] ?? a.kind}
                  {Object.keys(a.params).length > 0 && (
                    <span className="text-muted-foreground">
                      {" "}({Object.entries(a.params).map(([k, v]) => `${k}=${v}`).join(", ")})
                    </span>
                  )}
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {a.channels.join(" + ")}
                  {a.last_fired_at && ` · сработал ${new Date(a.last_fired_at).toLocaleString("ru-RU")}`}
                  {a.note && ` · ${a.note}`}
                </p>
              </div>
              <button className="text-xs text-[#ff3b30]"
                      onClick={async () => { await api.deleteAlert(a.id).catch(() => {}); refresh(); }}>
                Удалить
              </button>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
