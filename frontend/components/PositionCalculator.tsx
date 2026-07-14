"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, fmtMoney2, pretty, type PositionSizeResult } from "@/lib/api";

export function PositionCalculator({ instrument, defaultEntry }: {
  instrument: string | null;
  defaultEntry?: number | null;
}) {
  const [form, setForm] = useState({
    entry: "", stop_loss: "", balance: "", risk_pct: "1", leverage: "30",
    commission: "0", spread: "1",
  });
  const [result, setResult] = useState<PositionSizeResult | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const calc = async () => {
    if (!instrument) return;
    setBusy(true);
    try {
      const r = await api.positionSize({
        instrument,
        entry: parseFloat(form.entry) || (defaultEntry ?? 0),
        stop_loss: parseFloat(form.stop_loss) || 0,
        balance_eur: parseFloat(form.balance) || undefined,
        risk_pct: parseFloat(form.risk_pct) || undefined,
        leverage: parseFloat(form.leverage) || undefined,
        commission_eur: parseFloat(form.commission) || 0,
        spread_pips: parseFloat(form.spread) || 0,
      });
      setResult(r);
    } catch {
      setResult({ ok: false, error: "не удалось рассчитать" });
    }
    setBusy(false);
  };

  const field = (k: keyof typeof form, label: string, ph?: string) => (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      <Input className="rounded-xl" type="number" step="any" placeholder={ph}
             value={form[k]} onChange={set(k)} />
    </div>
  );

  return (
    <Card className="rounded-2xl border-black/5 shadow-sm">
      <CardContent className="pt-4">
        <h3 className="mb-2 text-sm font-semibold tracking-tight">
          Калькулятор позиции {instrument ? `· ${pretty(instrument)}` : ""}
        </h3>
        <div className="grid grid-cols-4 gap-3">
          {field("entry", "Вход", defaultEntry ? String(defaultEntry) : "")}
          {field("stop_loss", "Стоп-лосс")}
          {field("balance", "Баланс, € (пусто = из настроек)")}
          {field("risk_pct", "Риск, %")}
          {field("leverage", "Плечо")}
          {field("commission", "Комиссия, €")}
          {field("spread", "Спред, пунктов")}
          <div className="flex items-end">
            <Button className="w-full rounded-xl" onClick={calc}
                    disabled={busy || !instrument || !form.stop_loss}>
              {busy ? "Считаю…" : "Рассчитать"}
            </Button>
          </div>
        </div>

        {result && !result.ok && (
          <p className="mt-3 text-xs text-[#ff3b30]">{result.error}</p>
        )}
        {result?.ok && (
          <div className="mt-4 grid grid-cols-4 gap-3">
            <Stat label="Объём" value={`${result.units?.toLocaleString("ru-RU")} ед.`}
                  sub={`${result.lots} лота`} />
            <Stat label="Макс. убыток" value={fmtMoney2(result.max_loss_eur ?? 0)}
                  sub={`${result.risk_pct}% капитала`} tone="down" />
            <Stat label="Требуемая маржа" value={fmtMoney2(result.margin_eur ?? 0)}
                  sub={`номинал ${fmtMoney2(result.notional_eur ?? 0)}`} />
            <Stat label="Потенц. прибыль" value={result.potential_profit_eur != null ? fmtMoney2(result.potential_profit_eur) : "—"}
                  sub={`SL ${result.sl_pips} п. · спред ${fmtMoney2(result.spread_cost_eur ?? 0)}`} tone="up" />
          </div>
        )}
        {result?.ok && (result.warnings?.length ?? 0) > 0 && (
          <div className="mt-3 space-y-1">
            {result.warnings!.map((w, i) => (
              <p key={i} className="rounded-xl bg-amber-50 px-3 py-1.5 text-[11px] text-amber-900">⚠️ {w}</p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "up" | "down" }) {
  return (
    <div className="rounded-xl bg-black/[0.02] p-3">
      <p className="text-[10px] text-muted-foreground">{label}</p>
      <p className={`text-sm font-semibold tabular-nums ${
        tone === "up" ? "text-[#34c759]" : tone === "down" ? "text-[#ff3b30]" : ""}`}>
        {value}
      </p>
      {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
    </div>
  );
}
