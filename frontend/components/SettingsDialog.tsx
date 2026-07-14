"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import type { Settings } from "@/lib/api";

type Field = { key: keyof Settings; label: string; step: string; hint: string };

const STRATEGY_FIELDS: Field[] = [
  { key: "account_equity", label: "Капитал, €", step: "100", hint: "Для расчёта объёма позиции" },
  { key: "risk_per_trade_pct", label: "Риск на сделку, %", step: "0.1", hint: "Фиксированная доля капитала" },
  { key: "risk_reward", label: "Риск : прибыль", step: "0.1", hint: "TP = RR × дистанция SL" },
  { key: "sl_atr_multiple", label: "Стоп-лосс (× ATR14)", step: "0.1", hint: "Дистанция SL от входа" },
  { key: "min_score", label: "Порог сигнала", step: "0.05", hint: "Мин. |совокупная оценка|" },
  { key: "min_adx", label: "Мин. ADX (тренд)", step: "1", hint: "Ниже — флэтовый режим" },
  { key: "max_open_per_pair", label: "Макс. открытых / пара", step: "1", hint: "Одновременных сигналов" },
  { key: "cooldown_minutes", label: "Пауза, мин", step: "5", hint: "Между сигналами, пара+ТФ" },
  { key: "ai_weight", label: "Доля ИИ в формуле", step: "0.05", hint: "0 = только формулы, макс. 0.5" },
  { key: "leverage", label: "Плечо", step: "1", hint: "Для расчёта маржи" },
];

const SMART_FIELDS: Field[] = [
  { key: "trailing_atr_mult", label: "Трейлинг, × ATR14", step: "0.1", hint: "Дистанция скользящего стопа" },
  { key: "breakeven_at_r", label: "Безубыток при +R", step: "0.5", hint: "0 = не переносить SL в б/у" },
  { key: "partial_tp_at_r", label: "Частичная фиксация при +R", step: "0.5", hint: "Уровень частичного тейка" },
  { key: "partial_tp_fraction", label: "Доля фиксации", step: "0.1", hint: "0.5 = закрыть половину" },
];

const LIMIT_FIELDS: Field[] = [
  { key: "max_daily_loss", label: "Дневной лимит убытка, €", step: "50", hint: "0 = выключено" },
  { key: "max_daily_losses", label: "Убыточных сделок / день", step: "1", hint: "0 = выключено" },
  { key: "daily_profit_target", label: "Дневная цель прибыли, €", step: "50", hint: "Стоп после достижения" },
  { key: "max_drawdown_pct", label: "Макс. просадка, %", step: "1", hint: "От пика капитала" },
  { key: "max_weekly_loss", label: "Недельный лимит, €", step: "100", hint: "0 = выключено" },
  { key: "max_monthly_loss", label: "Месячный лимит, €", step: "100", hint: "0 = выключено" },
  { key: "max_open_risk_pct", label: "Открытый риск, %", step: "0.5", hint: "Суммарно по позициям" },
];

export function SettingsDialog({
  settings,
  onSave,
}: {
  settings: Settings | null;
  onSave: (patch: Partial<Settings>) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [halfKelly, setHalfKelly] = useState(false);
  const [trailing, setTrailing] = useState(false);
  const [partialTp, setPartialTp] = useState(false);
  const [saving, setSaving] = useState(false);

  const allFields = [...STRATEGY_FIELDS, ...SMART_FIELDS, ...LIMIT_FIELDS];

  useEffect(() => {
    if (settings && open) {
      setDraft(
        Object.fromEntries(allFields.map((f) => [f.key, String(settings[f.key])]))
      );
      setHalfKelly(settings.sizing_mode === "half_kelly");
      setTrailing(settings.trailing_enabled);
      setPartialTp(settings.partial_tp_enabled);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings, open]);

  const save = async () => {
    setSaving(true);
    const patch: Partial<Settings> = {
      sizing_mode: halfKelly ? "half_kelly" : "fixed",
      trailing_enabled: trailing,
      partial_tp_enabled: partialTp,
    };
    for (const f of allFields) {
      const v = parseFloat(draft[f.key]);
      if (!Number.isNaN(v)) (patch as Record<string, number | string | boolean>)[f.key] = v;
    }
    await onSave(patch);
    setSaving(false);
    setOpen(false);
  };

  const grid = (fields: Field[]) => (
    <div className="grid grid-cols-2 gap-4 py-2">
      {fields.map((f) => (
        <div key={f.key} className="space-y-1">
          <Label htmlFor={f.key} className="text-xs">{f.label}</Label>
          <Input
            id={f.key}
            type="number"
            step={f.step}
            className="rounded-xl"
            value={draft[f.key] ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
          />
          <p className="text-[10px] text-muted-foreground">{f.hint}</p>
        </div>
      ))}
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="rounded-xl">
          Стратегия
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto rounded-2xl sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle className="tracking-tight">Стратегия, риск и лимиты</DialogTitle>
          <DialogDescription>
            Все пороги питают детерминированный движок и риск-менеджер. Деньги — в евро.
          </DialogDescription>
        </DialogHeader>

        {grid(STRATEGY_FIELDS)}
        <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
          <div>
            <p className="text-sm font-medium">Размер позиции по ½ Келли</p>
            <p className="text-[10px] text-muted-foreground">
              f = (W − (1−W)/R) / 2 · нужно ≥ 20 закрытых сигналов, иначе фикс. %
            </p>
          </div>
          <Switch checked={halfKelly} onCheckedChange={setHalfKelly} />
        </div>

        <Separator />
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Умные SL/TP
        </p>
        <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
          <div>
            <p className="text-sm font-medium">Трейлинг-стоп по ATR</p>
            <p className="text-[10px] text-muted-foreground">Стоп подтягивается за ценой</p>
          </div>
          <Switch checked={trailing} onCheckedChange={setTrailing} />
        </div>
        <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
          <div>
            <p className="text-sm font-medium">Частичная фиксация прибыли</p>
            <p className="text-[10px] text-muted-foreground">Закрыть долю позиции на +N R</p>
          </div>
          <Switch checked={partialTp} onCheckedChange={setPartialTp} />
        </div>
        {grid(SMART_FIELDS)}

        <Separator />
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Дневные и периодные лимиты
        </p>
        <p className="text-[10px] text-muted-foreground">
          При достижении лимита новые сигналы блокируются до конца периода
          (день — UTC, неделя — с понедельника, месяц — календарный).
        </p>
        {grid(LIMIT_FIELDS)}

        <Button className="w-full rounded-xl" onClick={save} disabled={saving}>
          {saving ? "Сохраняю…" : "Сохранить"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
