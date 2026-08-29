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
import type { CategoryRisk, CategoryRiskOverrides, Settings } from "@/lib/api";
import { api } from "@/lib/api";

const CATEGORY_LABELS: Record<string, string> = {
  forex: "Форекс",
  metals: "Металлы",
  indices: "Индексы",
  energy: "Энергоносители",
  futures: "Фьючерсы",
  stocks: "Акции",
  etf: "ETF",
  crypto: "Криптовалюты",
};

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
  { key: "expiry_bars", label: "Выход по времени, баров", step: "1", hint: "Закрыть, если за N баров ни стоп, ни тейк (96 = выкл)" },
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
  { key: "max_currency_risk_pct", label: "Риск на валюту, %", step: "0.5", hint: "EUR/USD BUY + GBP/USD BUY = одна ставка против USD (0 = выкл)" },
  { key: "weekend_guard_min", label: "Стоп перед закрытием, мин", step: "15", hint: "Блок новых входов до пятницы 21:00 UTC (0 = выкл)" },
  { key: "weekend_close_min", label: "Закрыть позиции перед выходными, мин", step: "15", hint: "Принудительно закрыть открытые позиции до пятничного закрытия (0 = выкл)" },
  { key: "daily_cutoff_hour", label: "Стоп-час (Бухарест)", step: "1", hint: "После этого часа новые сделки не открываются (0 = выкл)" },
  { key: "quiet_resume_hour", label: "Возобновление, час", step: "1", hint: "Ночью сигналы не создаются; 9 = открытие Лондона" },
  { key: "max_risk_overshoot", label: "Допустимое превышение риска", step: "0.05", hint: "1.25 = терпим +25% из-за округления лота" },
  { key: "max_manual_overshoot", label: "Потолок ручного превышения", step: "0.5", hint: "До этого — кнопка со вторым подтверждением; выше — сделка не предлагается" },
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
  const [aggressiveMode, setAggressiveMode] = useState(false);
  const [trailing, setTrailing] = useState(false);
  const [partialTp, setPartialTp] = useState(false);
  const [saving, setSaving] = useState(false);
  const [categoryOverrides, setCategoryOverrides] = useState<CategoryRiskOverrides>({});
  const [categoryDraft, setCategoryDraft] = useState<Record<string, { risk_per_trade_pct: string; risk_reward: string }>>({});
  const [savingCategory, setSavingCategory] = useState<string | null>(null);
  const [blocked, setBlocked] = useState("");

  const allFields = [...STRATEGY_FIELDS, ...SMART_FIELDS, ...LIMIT_FIELDS];

  useEffect(() => {
    if (settings && open) {
      setDraft(
        Object.fromEntries(allFields.map((f) => [f.key, String(settings[f.key])]))
      );
      setHalfKelly(settings.sizing_mode === "half_kelly");
      setAggressiveMode(settings.signal_mode === "aggressive");
      setTrailing(settings.trailing_enabled);
      setPartialTp(settings.partial_tp_enabled);
      setBlocked((settings.blocked_instruments ?? []).join(", "));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings, open]);

  useEffect(() => {
    if (!open) return;
    api.categoryRisk().then((overrides) => {
      setCategoryOverrides(overrides);
      setCategoryDraft(
        Object.fromEntries(
          Object.entries(overrides).map(([cat, v]) => [
            cat,
            {
              risk_per_trade_pct: v?.risk_per_trade_pct != null ? String(v.risk_per_trade_pct) : "",
              risk_reward: v?.risk_reward != null ? String(v.risk_reward) : "",
            },
          ])
        )
      );
    });
  }, [open]);

  const saveCategory = async (category: string) => {
    setSavingCategory(category);
    const d = categoryDraft[category] ?? { risk_per_trade_pct: "", risk_reward: "" };
    const patch: CategoryRisk = {};
    const riskPct = parseFloat(d.risk_per_trade_pct);
    const rr = parseFloat(d.risk_reward);
    if (!Number.isNaN(riskPct)) patch.risk_per_trade_pct = riskPct;
    if (!Number.isNaN(rr)) patch.risk_reward = rr;
    const result = await api.saveCategoryRisk(category, patch);
    setCategoryOverrides((o) => ({ ...o, [category]: result[category] ?? null }));
    setSavingCategory(null);
  };

  const resetCategory = async (category: string) => {
    setSavingCategory(category);
    const result = await api.saveCategoryRisk(category, {});
    setCategoryOverrides((o) => ({ ...o, [category]: result[category] ?? null }));
    setCategoryDraft((d) => ({ ...d, [category]: { risk_per_trade_pct: "", risk_reward: "" } }));
    setSavingCategory(null);
  };

  const save = async () => {
    setSaving(true);
    const patch: Partial<Settings> = {
      sizing_mode: halfKelly ? "half_kelly" : "fixed",
      signal_mode: aggressiveMode ? "aggressive" : "conservative",
      trailing_enabled: trailing,
      partial_tp_enabled: partialTp,
      blocked_instruments: blocked
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean),
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
        <div className="flex items-center justify-between rounded-xl bg-[#ff9f0a]/10 p-3">
          <div>
            <p className="text-sm font-medium">⚡ Агрессивный режим</p>
            <p className="text-[10px] text-muted-foreground">
              Всегда ПОКУПКА/ПРОДАЖА по знаку оценки (никогда ОЖИДАНИЕ).
              Ниже порога — размер позиции ×0.5. Автоскан остаётся консервативным.
            </p>
          </div>
          <Switch checked={aggressiveMode} onCheckedChange={setAggressiveMode} />
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

        <div className="space-y-1 py-1">
          <Label htmlFor="blocked" className="text-xs">
            Отключённые инструменты
          </Label>
          <Input
            id="blocked"
            className="rounded-xl"
            placeholder="XPT_USD, XAG_USD"
            value={blocked}
            onChange={(e) => setBlocked(e.target.value)}
          />
          <p className="text-[10px] text-muted-foreground">
            Через запятую. Сигналы по ним не создаются вовсе — риск-менеджер
            отклоняет их до отправки.
          </p>
        </div>

        <Separator />
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Риск по категориям
        </p>
        <p className="text-[10px] text-muted-foreground">
          Своя пара риск% / RR для каждой категории вместо общих значений выше.
          Пусто = наследует общие настройки.
        </p>
        <div className="space-y-2 py-1">
          {Object.keys(categoryOverrides).map((cat) => {
            const d = categoryDraft[cat] ?? { risk_per_trade_pct: "", risk_reward: "" };
            const active = categoryOverrides[cat] != null;
            return (
              <div
                key={cat}
                className={`grid grid-cols-[1fr_auto_auto_auto] items-end gap-2 rounded-xl p-2 ${
                  active ? "bg-[#34c759]/10" : "bg-muted/50"
                }`}
              >
                <div className="space-y-1">
                  <Label className="text-xs">{CATEGORY_LABELS[cat] ?? cat}</Label>
                  <p className="text-[10px] text-muted-foreground">
                    {active ? "свой риск" : "общие настройки"}
                  </p>
                </div>
                <div className="w-20 space-y-1">
                  <Label className="text-[10px] text-muted-foreground">Риск %</Label>
                  <Input
                    type="number"
                    step="0.1"
                    className="h-8 rounded-lg text-xs"
                    placeholder={String(settings?.risk_per_trade_pct ?? "")}
                    value={d.risk_per_trade_pct}
                    onChange={(e) =>
                      setCategoryDraft((cd) => ({
                        ...cd,
                        [cat]: { ...d, risk_per_trade_pct: e.target.value },
                      }))
                    }
                  />
                </div>
                <div className="w-20 space-y-1">
                  <Label className="text-[10px] text-muted-foreground">RR</Label>
                  <Input
                    type="number"
                    step="0.1"
                    className="h-8 rounded-lg text-xs"
                    placeholder={String(settings?.risk_reward ?? "")}
                    value={d.risk_reward}
                    onChange={(e) =>
                      setCategoryDraft((cd) => ({
                        ...cd,
                        [cat]: { ...d, risk_reward: e.target.value },
                      }))
                    }
                  />
                </div>
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 rounded-lg px-2 text-xs"
                    disabled={savingCategory === cat}
                    onClick={() => saveCategory(cat)}
                  >
                    ✓
                  </Button>
                  {active && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 rounded-lg px-2 text-xs"
                      disabled={savingCategory === cat}
                      onClick={() => resetCategory(cat)}
                    >
                      ✕
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <Button className="w-full rounded-xl" onClick={save} disabled={saving}>
          {saving ? "Сохраняю…" : "Сохранить"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
