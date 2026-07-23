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
import type { AppConfig, Mt5Status } from "@/lib/api";
import { api } from "@/lib/api";

const PROVIDERS = [
  { value: "auto", label: "Авто (Twelve Data → EODHD → OANDA → симуляция)" },
  { value: "twelvedata", label: "Twelve Data" },
  { value: "eodhd", label: "EODHD" },
  { value: "oanda", label: "OANDA (legacy)" },
  { value: "simulation", label: "Симуляция" },
];

export function ConnectionsDialog({
  config,
  onSaved,
}: {
  config: AppConfig | null;
  onSaved: (cfg: AppConfig) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [provider, setProvider] = useState("auto");
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [autoscan, setAutoscan] = useState(false);
  const [stream, setStream] = useState(true);
  const [memoryOn, setMemoryOn] = useState(true);
  const [notifySignals, setNotifySignals] = useState(true);
  const [notifyAllMarkets, setNotifyAllMarkets] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [autotrade, setAutotrade] = useState(false);
  const [mt5Mirror, setMt5Mirror] = useState(false);
  const [riskSizing, setRiskSizing] = useState(false);
  const [mt5, setMt5] = useState<Mt5Status | null>(null);
  const [mt5Busy, setMt5Busy] = useState(false);
  const [mt5Msg, setMt5Msg] = useState<string | null>(null);

  useEffect(() => {
    if (config && open) {
      setDraft({
        twelvedata_api_key: config.twelvedata_api_key,
        eodhd_api_key: config.eodhd_api_key,
        oanda_api_key: config.oanda_api_key,
        oanda_account_id: config.oanda_account_id,
        anthropic_api_key: config.anthropic_api_key,
        telegram_bot_token: config.telegram_bot_token,
        telegram_chat_id: config.telegram_chat_id,
        news_times: config.news_times.join(", "),
        scan_interval_min: String(config.scan_interval_min),
        alert_email: config.alert_email,
        smtp_host: config.smtp_host,
        smtp_port: config.smtp_port,
        smtp_user: config.smtp_user,
        smtp_password: config.smtp_password,
        smtp_from: config.smtp_from,
        metaapi_token: config.metaapi_token,
        mt5_login: config.mt5_login,
        mt5_password: config.mt5_password,
        mt5_server: config.mt5_server,
        mt5_symbol_suffix: config.mt5_symbol_suffix,
        autotrade_min_confidence: String(config.autotrade_min_confidence),
        autotrade_max_positions: String(config.autotrade_max_positions),
        autotrade_lots: String(config.autotrade_lots),
        autotrade_orders_per_signal: String(config.autotrade_orders_per_signal),
        autotrade_max_lots: String(config.autotrade_max_lots),
      });
      setProvider(config.data_provider);
      setTelegramEnabled(config.telegram_enabled);
      setAutoscan(config.autoscan_enabled);
      setStream(config.stream_enabled);
      setMemoryOn(config.memory_enabled);
      setNotifySignals(config.notify_signals_enabled);
      setNotifyAllMarkets(config.notify_all_markets);
      setAutotrade(config.autotrade_enabled);
      setMt5Mirror(config.mt5_mirror_enabled);
      setRiskSizing(config.autotrade_risk_sizing);
      setTestResult(null);
      setMt5Msg(null);
      if (config.mt5_account_id) {
        api.mt5Status().then(setMt5).catch(() => setMt5(null));
      } else {
        setMt5(null);
      }
    }
  }, [config, open]);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setDraft((d) => ({ ...d, [k]: e.target.value }));

  const mt5Fields = () => ({
    metaapi_token: draft.metaapi_token,
    mt5_login: draft.mt5_login,
    mt5_password: draft.mt5_password,
    mt5_server: draft.mt5_server,
    mt5_symbol_suffix: draft.mt5_symbol_suffix,
    autotrade_enabled: autotrade,
    autotrade_min_confidence: parseInt(draft.autotrade_min_confidence) || 75,
    autotrade_max_positions: parseInt(draft.autotrade_max_positions) || 2,
    autotrade_lots: parseFloat(draft.autotrade_lots) || 0.01,
    autotrade_orders_per_signal: parseInt(draft.autotrade_orders_per_signal) || 1,
    mt5_mirror_enabled: mt5Mirror,
    autotrade_risk_sizing: riskSizing,
    autotrade_max_lots: parseFloat(draft.autotrade_max_lots) || 0.5,
  });

  const connectMt5 = async () => {
    setMt5Busy(true);
    setMt5Msg(null);
    try {
      // токен/логин должны попасть в базу до вызова connect
      const cfg = await api.saveConfig(mt5Fields());
      onSaved(cfg);
      const st = await api.mt5Connect();
      setMt5(st);
      setMt5Msg(st.connected ? "✅ MT5 подключён." : st.hint ?? "⏳ Счёт разворачивается…");
    } catch (e) {
      setMt5Msg(`❌ ${e instanceof Error ? e.message.slice(0, 160) : "ошибка"}`);
    }
    setMt5Busy(false);
  };

  const save = async () => {
    setSaving(true);
    try {
      const times = draft.news_times
        .split(",")
        .map((t) => t.trim())
        .filter((t) => /^\d{1,2}:\d{2}$/.test(t))
        .slice(0, 4);
      const cfg = await api.saveConfig({
        twelvedata_api_key: draft.twelvedata_api_key,
        eodhd_api_key: draft.eodhd_api_key,
        data_provider: provider as AppConfig["data_provider"],
        oanda_api_key: draft.oanda_api_key,
        oanda_account_id: draft.oanda_account_id,
        anthropic_api_key: draft.anthropic_api_key,
        telegram_bot_token: draft.telegram_bot_token,
        telegram_chat_id: draft.telegram_chat_id,
        telegram_enabled: telegramEnabled,
        autoscan_enabled: autoscan,
        stream_enabled: stream,
        memory_enabled: memoryOn,
        notify_signals_enabled: notifySignals,
        notify_all_markets: notifyAllMarkets,
        news_times: times.length ? times : undefined,
        scan_interval_min: parseInt(draft.scan_interval_min) || 15,
        alert_email: draft.alert_email,
        smtp_host: draft.smtp_host,
        smtp_port: draft.smtp_port,
        smtp_user: draft.smtp_user,
        smtp_password: draft.smtp_password,
        smtp_from: draft.smtp_from,
        ...mt5Fields(),
      });
      onSaved(cfg);
      setOpen(false);
    } catch {
      setTestResult("Не удалось сохранить настройки.");
    }
    setSaving(false);
  };

  const testTelegram = async () => {
    setTestResult(null);
    try {
      await api.telegramTest();
      setTestResult("✅ Сообщение отправлено в Telegram.");
    } catch (e) {
      setTestResult(`❌ ${e instanceof Error ? e.message.slice(0, 120) : "ошибка"}`);
    }
  };

  const detectChat = async () => {
    setTestResult(null);
    try {
      // токен должен быть сохранён до определения chat_id
      const cfg = await api.saveConfig({ telegram_bot_token: draft.telegram_bot_token });
      onSaved(cfg);
      const r = await api.telegramDetectChat();
      setDraft((d) => ({ ...d, telegram_chat_id: r.chat_id }));
      setTestResult(`✅ Найден чат: ${r.title || r.chat_id} (id ${r.chat_id}) — сохранено.`);
    } catch (e) {
      setTestResult(`❌ ${e instanceof Error ? e.message.slice(0, 160) : "ошибка"}`);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="rounded-xl">
          Подключения
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto rounded-2xl sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle className="tracking-tight">Подключения и расписание</DialogTitle>
          <DialogDescription>
            Ключи хранятся локально в базе приложения. Сохранённые значения показаны маской.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Котировки — Twelve Data (основной провайдер)
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Twelve Data API-ключ</Label>
              <Input className="rounded-xl" value={draft.twelvedata_api_key ?? ""}
                     onChange={set("twelvedata_api_key")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Источник данных</Label>
              <select className="h-9 w-full rounded-xl border bg-transparent px-2 text-sm"
                      value={provider} onChange={(e) => setProvider(e.target.value)}>
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground">
            REST + WebSocket: форекс, металлы, индексы, акции, ETF, крипто в
            реальном времени. Бесплатный ключ — twelvedata.com. Пусто = симуляция.
            {config && <> Активный источник: <b>{config.active_provider}</b>.</>}
          </p>
          <div className="space-y-1">
            <Label className="text-xs">EODHD API-ключ (дополнительный источник)</Label>
            <Input className="rounded-xl" value={draft.eodhd_api_key ?? ""}
                   onChange={set("eodhd_api_key")} />
            <p className="text-[10px] text-muted-foreground">
              Дневные свечи (включая индексы) + котировки. На бесплатном тарифе
              EODHD — только дневные данные, 20 запросов/день; внутридневные
              таймфреймы остаются на Twelve Data / симуляторе.
            </p>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
            <div>
              <p className="text-sm font-medium">WebSocket-поток цен</p>
              <p className="text-[10px] text-muted-foreground">
                Живые котировки избранного (нужен тариф TD с WS; иначе REST-опрос)
              </p>
            </div>
            <Switch checked={stream} onCheckedChange={setStream} />
          </div>

          <Separator />
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            OANDA (устаревший, опционально)
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">API-токен</Label>
              <Input className="rounded-xl" value={draft.oanda_api_key ?? ""} onChange={set("oanda_api_key")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">ID счёта</Label>
              <Input className="rounded-xl" value={draft.oanda_account_id ?? ""} onChange={set("oanda_account_id")} />
            </div>
          </div>

          <Separator />
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            MetaTrader 5 — торговля из приложения
          </p>
          <div className="space-y-1">
            <Label className="text-xs">Токен MetaApi</Label>
            <Input className="rounded-xl" value={draft.metaapi_token ?? ""} onChange={set("metaapi_token")} />
            <p className="text-[10px] text-muted-foreground">
              Мост к вашему счёту MT5 — бесплатный токен на metaapi.cloud
              (App → API access). Логин/пароль ниже — от торгового счёта MT5
              у вашего брокера (лучше начать с демо).
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Логин MT5</Label>
              <Input className="rounded-xl" value={draft.mt5_login ?? ""} onChange={set("mt5_login")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Пароль</Label>
              <Input className="rounded-xl" type="password" value={draft.mt5_password ?? ""} onChange={set("mt5_password")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Сервер брокера</Label>
              <Input className="rounded-xl" placeholder="ICMarketsSC-Demo" value={draft.mt5_server ?? ""} onChange={set("mt5_server")} />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Суффикс символов (если у брокера EURUSD.m и т.п.)</Label>
            <Input className="rounded-xl" placeholder="пусто, .m, .raw…" value={draft.mt5_symbol_suffix ?? ""} onChange={set("mt5_symbol_suffix")} />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="rounded-xl" onClick={connectMt5} disabled={mt5Busy}>
              {mt5Busy ? "Подключаю…" : "Подключить счёт"}
            </Button>
            {mt5Msg && <p className="self-center text-xs text-muted-foreground">{mt5Msg}</p>}
          </div>
          {mt5?.connected && mt5.account && (
            <div className="rounded-xl bg-[#34c759]/10 p-3 text-xs">
              <p className="font-medium text-[#34c759]">
                ✅ {mt5.login} · {mt5.server} · {mt5.account.broker}
              </p>
              <p className="mt-1 tabular-nums text-muted-foreground">
                Баланс {mt5.account.balance} {mt5.account.currency} · эквити{" "}
                {mt5.account.equity} · плечо 1:{mt5.account.leverage}
              </p>
            </div>
          )}
          {mt5 && !mt5.connected && mt5.state && (
            <p className="text-[10px] text-muted-foreground">
              Состояние счёта: {mt5.state} / {mt5.connection_status ?? "—"}
            </p>
          )}

          <div className="rounded-xl bg-muted/50 p-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">⚖️ Объём как на сайте</p>
                <p className="text-[10px] text-muted-foreground">
                  Лот считается из риск-менеджера (та же сумма риска, что в
                  статистике сайта), а не фиксированный. Итоги в MT5 совпадут
                  с цифрами приложения.
                </p>
              </div>
              <Switch checked={riskSizing} onCheckedChange={setRiskSizing} />
            </div>
            {riskSizing && (
              <div className="mt-2 w-40 space-y-1">
                <Label className="text-xs">Макс. лот (защита)</Label>
                <Input type="number" step="0.1" className="rounded-xl"
                       value={draft.autotrade_max_lots ?? "0.5"}
                       onChange={set("autotrade_max_lots")} />
              </div>
            )}
          </div>

          <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
            <div>
              <p className="text-sm font-medium">🪞 Зеркалировать сигналы в MT5</p>
              <p className="text-[10px] text-muted-foreground">
                Каждый созданный сигнал сразу открывает сделку в MT5 (лестница
                ордеров по уверенности); безубыток и трейлинг двигают SL у
                брокера, истечение сигнала закрывает позицию
              </p>
            </div>
            <Switch checked={mt5Mirror} onCheckedChange={setMt5Mirror} />
          </div>

          <div className="rounded-xl border border-[#ff9f0a]/40 bg-[#ff9f0a]/10 p-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">🤖 Автоторговля</p>
                <p className="text-[10px] text-muted-foreground">
                  Робот сам открывает позиции в MT5 по сигналам автосканера;
                  безубыток/трейлинг двигают SL у брокера, истечение закрывает
                </p>
              </div>
              <Switch checked={autotrade} onCheckedChange={setAutotrade} />
            </div>
            <p className="mt-2 text-[10px] leading-4 text-[#b25e00] dark:text-[#ff9f0a]">
              Включая автоторговлю, вы принимаете на себя всю ответственность за
              сделки и возможные убытки. Позиция открывается только когда сигнал
              прошёл риск-менеджер и уверенность движка не ниже порога; SL/TP
              ставятся сразу в ордере. Начните с демо-счёта и минимального лота.
            </p>
            {autotrade && (
              <>
                <div className="mt-2 grid grid-cols-4 gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs">Мин. уверенность, %</Label>
                    <Input type="number" className="rounded-xl" value={draft.autotrade_min_confidence ?? "75"} onChange={set("autotrade_min_confidence")} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Лот на сделку</Label>
                    <Input type="number" step="0.01" className="rounded-xl" value={draft.autotrade_lots ?? "0.01"} onChange={set("autotrade_lots")} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Макс. позиций</Label>
                    <Input type="number" className="rounded-xl" value={draft.autotrade_max_positions ?? "2"} onChange={set("autotrade_max_positions")} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Ордеров на сигнал</Label>
                    <Input type="number" min="1" max="5" className="rounded-xl" value={draft.autotrade_orders_per_signal ?? "1"} onChange={set("autotrade_orders_per_signal")} />
                  </div>
                </div>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  Если ордеров &gt; 1: при уверенности на пороге откроется 1 ордер,
                  +1 за каждые 8 п.п. сверх порога. Тейки ступенями: первый ордер
                  фиксирует +1R, второй — цель сигнала, третий бежит на цель ×1.5;
                  стоп-лосс общий.
                </p>
              </>
            )}
          </div>

          <Separator />
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Anthropic (ИИ-агенты)
          </p>
          <div className="space-y-1">
            <Label className="text-xs">API-ключ</Label>
            <Input className="rounded-xl" value={draft.anthropic_api_key ?? ""} onChange={set("anthropic_api_key")} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Время запусков анализа (UTC, через запятую)</Label>
            <Input className="rounded-xl" placeholder="07:00, 13:30" value={draft.news_times ?? ""} onChange={set("news_times")} />
            <p className="text-[10px] text-muted-foreground">
              1–2 запуска в день ≈ 3 вызова API за запуск — расход минимален.
            </p>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
            <div>
              <p className="text-sm font-medium">ИИ-память (обучение на опыте)</p>
              <p className="text-[10px] text-muted-foreground">
                Разборы сделок, уроки, статистика факторов — подмешиваются в промпты
              </p>
            </div>
            <Switch checked={memoryOn} onCheckedChange={setMemoryOn} />
          </div>

          <Separator />
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Telegram (уведомления)
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Токен бота</Label>
              <Input className="rounded-xl" value={draft.telegram_bot_token ?? ""} onChange={set("telegram_bot_token")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Chat ID / @канал</Label>
              <Input className="rounded-xl" placeholder="@my_channel" value={draft.telegram_chat_id ?? ""} onChange={set("telegram_chat_id")} />
            </div>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
            <div>
              <p className="text-sm font-medium">Отправлять сигналы в Telegram</p>
              <p className="text-[10px] text-muted-foreground">Новые сигналы и их результаты</p>
            </div>
            <Switch checked={telegramEnabled} onCheckedChange={setTelegramEnabled} />
          </div>
          <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
            <div>
              <p className="text-sm font-medium">Уведомления об уверенных сигналах</p>
              <p className="text-[10px] text-muted-foreground">
                Пуш в приложение (и Telegram), когда движок уверен по инструменту
                из «Избранного» — 15m/1h/4h, не чаще раза в час
              </p>
            </div>
            <Switch checked={notifySignals} onCheckedChange={setNotifySignals} />
          </div>
          <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
            <div>
              <p className="text-sm font-medium">🔭 Сигналы по всем рынкам</p>
              <p className="text-[10px] text-muted-foreground">
                Раз в 30 минут сканировать форекс/металлы/индексы/крипту ВНЕ
                «Избранного» (1h) и пушить, когда движок уверен во входе
              </p>
            </div>
            <Switch checked={notifyAllMarkets} onCheckedChange={setNotifyAllMarkets} />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="rounded-xl" onClick={detectChat}>
              Найти chat ID
            </Button>
            <Button variant="outline" size="sm" className="rounded-xl" onClick={testTelegram}>
              Тест сообщения
            </Button>
          </div>
          {testResult && <p className="text-xs text-muted-foreground">{testResult}</p>}
          <p className="text-[10px] text-muted-foreground">
            «Найти chat ID»: сначала напишите вашему боту любое сообщение в
            Telegram, затем нажмите — id подставится сам. Ник бота
            (@имя_бота) в поле chat_id не работает.
          </p>

          <Separator />
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            E-mail (доставка алертов)
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Адрес получателя</Label>
              <Input className="rounded-xl" placeholder="you@mail.com" value={draft.alert_email ?? ""} onChange={set("alert_email")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">SMTP-хост</Label>
              <Input className="rounded-xl" placeholder="smtp.gmail.com" value={draft.smtp_host ?? ""} onChange={set("smtp_host")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Порт</Label>
              <Input className="rounded-xl" placeholder="587" value={draft.smtp_port ?? ""} onChange={set("smtp_port")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Пользователь</Label>
              <Input className="rounded-xl" value={draft.smtp_user ?? ""} onChange={set("smtp_user")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Пароль</Label>
              <Input className="rounded-xl" type="password" value={draft.smtp_password ?? ""} onChange={set("smtp_password")} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">От кого (From)</Label>
              <Input className="rounded-xl" value={draft.smtp_from ?? ""} onChange={set("smtp_from")} />
            </div>
          </div>

          <Separator />
          <div className="flex items-center justify-between rounded-xl bg-muted/50 p-3">
            <div>
              <p className="text-sm font-medium">Автосканирование пар</p>
              <p className="text-[10px] text-muted-foreground">
                Проверять список пар и создавать сигналы автоматически
              </p>
            </div>
            <Switch checked={autoscan} onCheckedChange={setAutoscan} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Интервал сканирования, мин</Label>
            <Input type="number" className="rounded-xl" value={draft.scan_interval_min ?? "15"} onChange={set("scan_interval_min")} />
          </div>
        </div>

        <Button className="mt-2 w-full rounded-xl" onClick={save} disabled={saving}>
          {saving ? "Сохраняю…" : "Сохранить"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
