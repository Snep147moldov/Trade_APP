"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bell, CandlestickChart, ChartCandlestick, History, LayoutDashboard,
  LayoutGrid, ListOrdered, Map, Newspaper, NotebookPen, Plug, Search,
  ShieldAlert, ShieldCheck, Sparkles, User, Wallet, Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AppShell, type NavNode } from "@/components/AppShell";
import { AlertToast } from "@/components/AlertToast";
import { DashboardView } from "@/components/DashboardView";
import { SettingsCard, SettingsSection } from "@/components/SettingsSheet";
import { AccountDialog } from "@/components/AccountDialog";
import { AdminDialog } from "@/components/AdminDialog";
import { AlertsDialog } from "@/components/AlertsDialog";
import { AssistantChat } from "@/components/AssistantChat";
import { AuthGate } from "@/components/AuthGate";
import { BacktestPanel } from "@/components/BacktestPanel";
import { Button } from "@/components/ui/button";
import { CalendarCard } from "@/components/CalendarCard";
import { CandleCountdown } from "@/components/CandleCountdown";
import { ConnectionsDialog } from "@/components/ConnectionsDialog";
import { HeatmapPanel } from "@/components/HeatmapPanel";
import { HistoryTable } from "@/components/HistoryTable";
import { InvestPanel } from "@/components/InvestPanel";
import { JournalPanel } from "@/components/JournalPanel";
import { MarketClock } from "@/components/MarketClock";
import { MemoryPanel } from "@/components/MemoryPanel";
import { MultiChartGrid } from "@/components/MultiChartGrid";
import { NewsPanel } from "@/components/NewsPanel";
import { NotificationsBell } from "@/components/NotificationsBell";
import { OrderBookPanel } from "@/components/OrderBookPanel";
import { PairPicker } from "@/components/PairPicker";
import { PatternsPanel } from "@/components/PatternsPanel";
import { PositionCalculator } from "@/components/PositionCalculator";
import {
  ChartControlsBar, DEFAULT_TOGGLES, DrawToolbar, PriceChart,
  type ChartToggles, type DrawMode,
} from "@/components/PriceChart";
import { RiskPanel } from "@/components/RiskPanel";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { ScreenerPanel } from "@/components/ScreenerPanel";
import { SettingsDialog } from "@/components/SettingsDialog";
import { SignalCard } from "@/components/SignalCard";
import { UsageCard } from "@/components/UsageCard";
import {
  api,
  pretty,
  type Analysis,
  type AppConfig,
  type AuthUser,
  type CalendarEvent,
  type InstrumentsResult,
  type NewsResult,
  type PatternsResult,
  type Quote,
  type Settings,
  type SignalRow,
  type SignalStats,
  type UsageStats,
} from "@/lib/api";

const TIMEFRAMES = ["1m", "5m", "15m", "40m", "1h", "4h", "1d"];

// Дерево разделов. Раньше девять вкладок стояли в один ряд, а «Обзор» держал
// в себе половину приложения — график, сигнал, разбор оценки, новости, капитал
// и всю историю сделок одной лентой на несколько экранов. Теперь у каждого
// экрана своя страница, а родственные собраны в разделы.
const VIEWS: NavNode[] = [
  { key: "dashboard", label: "Дашборд", icon: LayoutDashboard },
  {
    key: "trading",
    label: "Торговля",
    icon: ChartCandlestick,
    children: [
      { key: "chart", label: "График и сигнал", icon: CandlestickChart },
      { key: "multi", label: "Несколько пар", icon: LayoutGrid },
      { key: "depth", label: "Стакан", icon: ListOrdered },
    ],
  },
  {
    key: "analytics",
    label: "Аналитика",
    icon: Sparkles,
    children: [
      { key: "patterns", label: "Паттерны", icon: Sparkles },
      { key: "assistant", label: "Ассистент", icon: Sparkles },
      { key: "news", label: "Новости", icon: Newspaper },
      { key: "screener", label: "Скринер", icon: Search },
      { key: "heatmap", label: "Карта рынка", icon: Map },
    ],
  },
  {
    key: "money",
    label: "Риск и капитал",
    icon: ShieldAlert,
    children: [
      { key: "risk", label: "Лимиты", icon: ShieldAlert },
      { key: "calc", label: "Калькулятор", icon: Wallet },
      { key: "capital", label: "Капитал и расходы", icon: Wallet },
    ],
  },
  {
    key: "records",
    label: "История",
    icon: NotebookPen,
    children: [
      { key: "trades", label: "Сделки", icon: NotebookPen },
      { key: "journal", label: "Дневник", icon: NotebookPen },
      { key: "backtest", label: "Бэктест", icon: History },
    ],
  },
];

// Нижняя панель телефона: до этих четырёх дотягивается большой палец
const MOBILE_KEYS = ["dashboard", "chart", "risk", "trades"];

function Dashboard({ user, logout }: { user: AuthUser; logout: () => void }) {
  const [me, setMe] = useState<AuthUser>(user);
  const [view, setView] = useState("dashboard");
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [instruments, setInstruments] = useState<InstrumentsResult | null>(null);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [instrument, setInstrument] = useState<string | null>(null);
  const [tf, setTf] = useState("15m");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [patterns, setPatterns] = useState<PatternsResult | null>(null);
  const [toggles, setToggles] = useState<ChartToggles>(DEFAULT_TOGGLES);
  const [drawMode, setDrawMode] = useState<DrawMode>("none");
  const [drawVersion, setDrawVersion] = useState(0);
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [news, setNews] = useState<NewsResult | null>(null);
  const [calendar, setCalendar] = useState<CalendarEvent[]>([]);
  const [alerts, setAlerts] = useState<CalendarEvent[]>([]);
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [stats, setStats] = useState<SignalStats | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [runningNews, setRunningNews] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshSignals = useCallback(async () => {
    try {
      const d = await api.signals();
      setSignals(d.signals);
      setStats(d.stats);
    } catch {
      /* handled elsewhere */
    }
  }, []);

  const refreshCalendar = useCallback(async () => {
    try {
      const c = await api.calendar();
      setCalendar(c.events);
      setAlerts(c.alerts);
    } catch {
      /* ignore */
    }
  }, []);

  const refreshMeta = useCallback(async () => {
    try {
      const [cfg, ins, n, st, us] = await Promise.all([
        api.config(),
        api.instruments(),
        api.news(),
        api.settings(),
        api.usage(),
      ]);
      setConfig(cfg);
      setInstruments(ins);
      setWatchlist(ins.watchlist);
      setNews(n);
      setSettings(st);
      setUsage(us);
      setInstrument((cur) => cur ?? ins.watchlist[0] ?? null);
    } catch {
      setError("Бэкенд недоступен — запущен ли uvicorn на порту 8000?");
    }
  }, []);

  const refreshAnalysis = useCallback(async () => {
    if (!instrument) return;
    try {
      setError(null);
      const [a, p] = await Promise.all([
        api.analysis(instrument, tf),
        api.patterns(instrument, tf).catch(() => null),
      ]);
      setAnalysis(a);
      setPatterns(p);
    } catch {
      setError("Бэкенд недоступен — запущен ли uvicorn на порту 8000?");
    } finally {
      setLoading(false);
    }
  }, [instrument, tf]);

  const refreshQuotes = useCallback(async () => {
    if (watchlist.length === 0) return;
    try {
      setQuotes((await api.quotes(watchlist)).quotes);
    } catch {
      /* ignore */
    }
  }, [watchlist]);

  useEffect(() => {
    refreshMeta();
    refreshSignals();
    refreshCalendar();
    const id = setInterval(refreshCalendar, 60_000);
    return () => clearInterval(id);
  }, [refreshMeta, refreshSignals, refreshCalendar]);

  useEffect(() => {
    refreshQuotes();
    const id = setInterval(refreshQuotes, 10_000);
    return () => clearInterval(id);
  }, [refreshQuotes]);

  // live tick: only the selected instrument, every 3s — moves the forming candle
  useEffect(() => {
    if (!instrument) return;
    const fast = async () => {
      try {
        const q = await api.quotes([instrument]);
        setQuotes((prev) => ({ ...prev, ...q.quotes }));
      } catch {
        /* ignore */
      }
    };
    const id = setInterval(fast, 3_000);
    return () => clearInterval(id);
  }, [instrument]);

  useEffect(() => {
    if (!instrument) return;
    setLoading(true);
    setAnalysis(null);
    setPatterns(null);
    refreshAnalysis();
    const id = setInterval(refreshAnalysis, 30_000);
    return () => clearInterval(id);
  }, [refreshAnalysis, instrument]);

  const saveWatchlist = async (list: string[]) => {
    const r = await api.saveWatchlist(list);
    setWatchlist(r.watchlist);
    if (!instrument || !r.watchlist.includes(instrument)) {
      setInstrument(r.watchlist[0] ?? null);
    }
    refreshCalendar();
  };

  const generate = async () => {
    if (!instrument) return;
    setGenerating(true);
    setLastResult(null);
    try {
      const r = await api.generateSignal(instrument, tf);
      const mt5Note = r.mt5
        ? r.mt5.ok
          ? ` · MT5: открыто ×${r.mt5.opened}${r.mt5.error ? ` (${r.mt5.error})` : ""}`
          : ` · MT5: ${r.mt5.error ?? "ошибка"}`
        : "";
      setLastResult(
        r.created
          ? `Сигнал #${r.signal_id} отслеживается${r.telegram_sent ? " · отправлен в Telegram" : ""}${mt5Note}.`
          : `Не сохранён: ${r.analysis.risk.reasons.join("; ")}`
      );
      await refreshSignals();
    } catch {
      setLastResult("Не удалось сохранить сигнал.");
    }
    setGenerating(false);
  };

  const evaluate = async () => {
    setEvaluating(true);
    try {
      await api.evaluate();
      await refreshSignals();
    } catch {
      /* ignore */
    }
    setEvaluating(false);
  };

  const runNews = async () => {
    setRunningNews(true);
    try {
      setNews(await api.runNews());
      setUsage(await api.usage());
    } catch (e) {
      setLastResult(e instanceof Error ? e.message.slice(0, 140) : "Ошибка ИИ-анализа");
    }
    setRunningNews(false);
  };

  const pickAndShow = (symbol: string) => {
    setInstrument(symbol);
    setView("chart");
  };

  const groups = instruments?.groups;
  const openCount = signals.filter((x) => x.status === "open").length;
  const aiEnabled = config?.ai_enabled ?? false;
  const liveQuote = instrument ? quotes[instrument] : undefined;

  const sidebarContent = (
    <div className="space-y-4">
          <div>
            <p className="mb-2 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Избранное
            </p>
            {watchlist.length === 0 ? (
              <p className="rounded-xl bg-card/60 p-3 text-xs text-muted-foreground">
                Список пуст — выберите инструменты: форекс, металлы, индексы,
                акции, крипто…
              </p>
            ) : (
              <nav className="space-y-0.5">
                {watchlist.map((ins) => (
                  <button
                    key={ins}
                    onClick={() => pickAndShow(ins)}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition-colors ${
                      ins === instrument
                        ? "bg-card font-semibold shadow-sm"
                        : "text-muted-foreground hover:bg-card/60"
                    }`}
                  >
                    <span>{pretty(ins)}</span>
                    {quotes[ins] && (
                      <span className="text-[10px] tabular-nums text-muted-foreground">
                        {quotes[ins].price}
                      </span>
                    )}
                  </button>
                ))}
              </nav>
            )}
            <div className="mt-2">
              <PairPicker
                data={instruments}
                watchlist={watchlist}
                onSave={saveWatchlist}
                onCatalogChange={() => api.instruments().then(setInstruments).catch(() => {})}
              />
            </div>
          </div>

          {groups && groups.volatile.length > 0 && (
            <div>
              <p className="mb-2 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Высокая волатильность
              </p>
              <div className="space-y-0.5">
                {groups.volatile.slice(0, 6).map((v) => (
                  <button
                    key={v.symbol}
                    onClick={() => pickAndShow(v.symbol)}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-1.5 text-left text-xs transition-colors ${
                      v.symbol === instrument
                        ? "bg-card font-semibold shadow-sm"
                        : "text-muted-foreground hover:bg-card/60"
                    }`}
                  >
                    <span>{pretty(v.symbol)}</span>
                    <span className="tabular-nums text-warn">{v.atr_pct}%</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {groups && groups.ai_recommended.length > 0 && (
            <div>
              <p className="mb-2 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                ИИ рекомендует
              </p>
              <div className="space-y-0.5">
                {groups.ai_recommended.slice(0, 6).map((v) => (
                  <button
                    key={v.symbol}
                    onClick={() => pickAndShow(v.symbol)}
                    title={v.rationale}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-1.5 text-left text-xs transition-colors ${
                      v.symbol === instrument
                        ? "bg-card font-semibold shadow-sm"
                        : "text-muted-foreground hover:bg-card/60"
                    }`}
                  >
                    <span>{pretty(v.symbol)}</span>
                    <span className={`tabular-nums ${v.bias > 0 ? "text-pos" : "text-neg"}`}>
                      {v.bias > 0 ? "▲" : "▼"} {Math.abs(v.bias).toFixed(2)}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
    </div>
  );

  const banner = <AlertToast alerts={alerts} />;

  return (
    <AppShell
      nav={VIEWS.map((v) =>
        // счётчик открытых сигналов виден прямо в меню: раньше, чтобы узнать,
        // висит ли что-то незакрытое, приходилось открывать журнал
        v.children
          ? {
              ...v,
              children: v.children.map((c) =>
                c.key === "trades" ? { ...c, badge: openCount } : c,
              ),
            }
          : v,
      )}
      mobileKeys={MOBILE_KEYS}
      view={view}
      onView={setView}
      onLogout={logout}
      brand={
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="h-2.5 w-2.5 shrink-0 rounded-full bg-brand" />
          <span className="truncate text-[15px] font-semibold tracking-tight">
            Codnixy AI Trade
          </span>
        </div>
      }
      headerRight={
        <>
          <div className="hidden md:block">
            <MarketClock />
          </div>
          {/* статус провайдера и ИИ — справка, а не действие: на телефоне
              уступают место кнопкам */}
          <div className="hidden shrink-0 items-center gap-2 md:flex">
            {config?.simulated_data ? (
              <Badge variant="secondary" className="rounded-full text-[10px]">
                Симуляция
              </Badge>
            ) : (
              <Badge variant="secondary" className="rounded-full bg-brand/10 text-[10px] text-brand-ink">
                {config?.active_provider === "twelvedata" ? "Twelve Data" : config?.active_provider}
              </Badge>
            )}
            <Badge
              variant="secondary"
              className={`rounded-full text-[10px] ${
                aiEnabled ? "bg-pos/10 text-pos" : ""
              }`}
            >
              {aiEnabled ? "ИИ" : "ИИ выкл."}
            </Badge>
          </div>
          <NotificationsBell onPick={pickAndShow} />
          {/* «Стратегия» остаётся снаружи: её открывают по ходу торговли, а не
              раз в месяц, как ключи и почту */}
          <SettingsDialog
            settings={settings}
            onSave={async (patch) => {
              setSettings(await api.saveSettings(patch));
              await refreshSignals();
            }}
          />
        </>
      }
      sidebar={sidebarContent}
      banner={banner}
      settings={
        <>
          <SettingsSection title="Счёт">
            <AccountDialog
              user={me}
              onUserChange={setMe}
              trigger={<SettingsCard icon={User} label="Аккаунт" hint={me.username} />}
            />
            <ConnectionsDialog
              config={config}
              onSaved={(c) => { setConfig(c); refreshMeta(); }}
              trigger={
                <SettingsCard
                  icon={Plug}
                  label="Подключения"
                  hint={
                    config?.mt5_account_id
                      ? `${config.active_provider} · MT5 ${config.mt5_login}`
                      : config?.active_provider || "не настроено"
                  }
                />
              }
            />
          </SettingsSection>

          <SettingsSection title="Торговля">
            <SettingsCard
              icon={Zap}
              label="Стратегия"
              hint={`порог ${settings?.min_score ?? "—"} · R:R ${settings?.risk_reward ?? "—"}`}
              tone="brand"
              onClick={() => {
                // диалог стратегии живёт в шапке — открываем его же кнопку
                const btn = document.querySelector<HTMLButtonElement>(
                  "[data-strategy-trigger]",
                );
                btn?.click();
              }}
            />
            <AlertsDialog
              watchlist={watchlist}
              instrument={instrument}
              trigger={
                <SettingsCard
                  icon={Bell}
                  label="Алерты"
                  hint={`${watchlist.length} пар в избранном`}
                />
              }
            />
          </SettingsSection>

          <SettingsSection title="Риск">
            <SettingsCard
              icon={ShieldCheck}
              label="Лимиты"
              hint={`открытый риск ≤ ${settings?.max_open_risk_pct ?? "—"}%`}
              onClick={() => setView("risk")}
            />
            <SettingsCard
              icon={Wallet}
              label="Капитал"
              hint={`риск ${settings?.risk_per_trade_pct ?? "—"}% на сделку`}
              onClick={() => setView("capital")}
            />
          </SettingsSection>

          {me.role === "admin" && (
            <SettingsSection title="Администрирование">
              <AdminDialog
                me={me}
                trigger={<SettingsCard icon={ShieldAlert} label="Пользователи" hint="доступ и журнал" />}
              />
            </SettingsSection>
          )}
        </>
      }
      fab={
        <button
          type="button"
          onClick={generate}
          disabled={generating || !instrument}
          title={instrument ? `Сигнал по ${pretty(instrument)}` : "Сначала выберите инструмент"}
          className="flex h-14 w-14 items-center justify-center rounded-full bg-brand text-white shadow-pop transition-all duration-200 hover:scale-105 active:scale-95 disabled:opacity-40"
        >
          <Zap className={`h-5 w-5 ${generating ? "animate-pulse" : ""}`} />
        </button>
      }
    >
      <div className="h-full min-h-0">
        {view === "dashboard" && (
          <DashboardView
            stats={stats}
            signals={signals}
            settings={settings}
            username={me.username}
            onGo={setView}
            onPick={pickAndShow}
          />
        )}

        {view === "chart" &&
          (instrument ? (
            <div className="grid h-full min-h-0 grid-cols-1 items-start gap-3 xl:grid-cols-[1fr_360px]">
              <div className="min-h-0">
                <Card className="rounded-2xl border-border shadow-sm">
                                      <CardContent className="pt-4">
                                        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                                          <div>
                                            <h2 className="text-lg font-semibold tracking-tight">
                                              {pretty(instrument)}
                                              {liveQuote && (
                                                <span className="ml-2 text-sm font-normal tabular-nums text-muted-foreground">
                                                  {liveQuote.price}
                                                  {liveQuote.source === "ws" && (
                                                    <span className="ml-1 text-[9px] text-pos">● live</span>
                                                  )}
                                                </span>
                                              )}
                                              <span className="ml-3">
                                                <CandleCountdown tf={tf} onExpire={refreshAnalysis} />
                                              </span>
                                            </h2>
                                            {analysis && (
                                              <p className="text-sm tabular-nums text-muted-foreground">
                                                {analysis.indicators.adx14 != null && (
                                                  <span className="text-xs">
                                                    ADX {Number(analysis.indicators.adx14).toFixed(1)} · RSI{" "}
                                                    {Number(analysis.indicators.rsi14 ?? 0).toFixed(0)} · Hurst{" "}
                                                    {analysis.indicators.hurst} · {analysis.regime === "trending" ? "тренд" : "флэт"}
                                                  </span>
                                                )}
                                              </p>
                                            )}
                                          </div>
                                          <Tabs value={tf} onValueChange={setTf} className="no-scrollbar -mx-1 max-w-full overflow-x-auto px-1">
                                            <TabsList className="rounded-xl">
                                              {TIMEFRAMES.map((t) => (
                                                <TabsTrigger key={t} value={t} className="rounded-lg px-3">
                                                  {t}
                                                </TabsTrigger>
                                              ))}
                                            </TabsList>
                                          </Tabs>
                                        </div>
                                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                                          <div className="no-scrollbar -mx-1 max-w-full overflow-x-auto px-1">
                                            <ChartControlsBar toggles={toggles} onChange={setToggles} />
                                          </div>
                                          <div className="no-scrollbar -mx-1 max-w-full overflow-x-auto px-1">
                                            <DrawToolbar
                                              instrument={instrument}
                                              timeframe={tf}
                                              mode={drawMode}
                                              onMode={setDrawMode}
                                              onChanged={() => setDrawVersion((v) => v + 1)}
                                            />
                                          </div>
                                        </div>
                                        {error ? (
                                          <div className="flex h-[420px] items-center justify-center text-sm text-muted-foreground">
                                            {error}
                                          </div>
                                        ) : loading || !analysis ? (
                                          <div className="flex h-[420px] items-center justify-center text-sm text-muted-foreground">
                                            Загружаю {pretty(instrument)} · {tf}…
                                          </div>
                                        ) : (
                                          <PriceChart
                                            analysis={analysis}
                                            patterns={patterns}
                                            toggles={toggles}
                                            livePrice={liveQuote?.price ?? null}
                                            drawMode={drawMode}
                                            drawVersion={drawVersion}
                                            onDrawingAdded={() => setDrawVersion((v) => v + 1)}
                                          />
                                        )}
                                        <p className="mt-2 text-[10px] text-muted-foreground">
                                          <span className="text-brand-ink">—</span> EMA 20&nbsp;&nbsp;
                                          <span className="text-warn">—</span> EMA 50 · время локальное
                                          {analysis && analysis.direction !== "HOLD" && " · пунктир: вход / SL / TP"}
                                        </p>
                                      </CardContent>
                                    </Card>
              </div>
              <div className="scrollbar-thin min-h-0 space-y-3 xl:h-full xl:overflow-y-auto">
                <SignalCard
                                      analysis={analysis}
                                      onGenerate={generate}
                                      generating={generating}
                                      lastResult={lastResult}
                                      signalMode={settings?.signal_mode ?? "conservative"}
                                      onToggleMode={async (v) => {
                                        setSettings(await api.saveSettings({
                                          signal_mode: v ? "aggressive" : "conservative",
                                        }));
                                        await refreshAnalysis();
                                      }}
                                      mt5Ready={Boolean(config?.mt5_account_id)}
                                      mt5Lots={config?.autotrade_lots}
                                      onMt5Trade={async (orders) => {
                                        if (!analysis || analysis.direction === "HOLD") {
                                          return "Нет направления для сделки.";
                                        }
                                        const r = await api.mt5Trade({
                                          instrument: analysis.instrument,
                                          direction: analysis.direction,
                                          stop_loss: analysis.levels.stop_loss,
                                          take_profit: analysis.levels.take_profit,
                                          orders,
                                        });
                                        const opened = r.orders_opened ?? 1;
                                        const tps = r.take_profits?.join(", ");
                                        return opened > 1
                                          ? `✅ MT5: ${r.symbol} ${analysis.direction} ×${opened} по ${r.lots} лот · TP ${tps}.${r.partial_error ? ` ⚠️ ${r.partial_error}` : ""}`
                                          : `✅ MT5: ${r.symbol} ${analysis.direction} ${r.lots} лот, позиция ${r.position_id ?? r.order_id ?? "открыта"}.${r.partial_error ? ` ⚠️ ${r.partial_error}` : ""}`;
                                      }}
                                    />
                <ScoreBreakdown analysis={analysis} />
              </div>
            </div>
          ) : (
            <Card className="rounded-2xl border-border shadow-sm">
                                <CardContent className="flex h-[300px] flex-col items-center justify-center gap-2 text-center">
                                  <p className="text-lg font-semibold tracking-tight">
                                    Добро пожаловать, {me.username}
                                  </p>
                                  <p className="max-w-md text-sm text-muted-foreground">
                                    Начните с выбора инструментов слева — доступны форекс,
                                    металлы, индексы, энергоносители, фьючерсы, акции, ETF и
                                    криптовалюты. Ничего не предустановлено.
                                  </p>
                                </CardContent>
                              </Card>
          ))}

        {view === "multi" && (
          <div className="stretch h-full min-h-0">
            <MultiChartGrid watchlist={watchlist} />
          </div>
        )}

        {view === "depth" && (
          <div className="stretch h-full min-h-0">
            <OrderBookPanel instrument={instrument} tf={tf} />
          </div>
        )}

        {view === "patterns" && (
          <div className="stretch h-full min-h-0">
            <PatternsPanel instrument={instrument} patterns={patterns} aiEnabled={aiEnabled} />
          </div>
        )}

        {view === "assistant" && (
          <div className="stretch grid h-full min-h-0 grid-cols-1 gap-3 lg:grid-cols-2">
            <AssistantChat instrument={instrument} timeframe={tf} aiEnabled={aiEnabled} />
            <MemoryPanel aiEnabled={aiEnabled} />
          </div>
        )}

        {view === "news" && (
          <div className="stretch grid h-full min-h-0 grid-cols-1 gap-3 lg:grid-cols-2">
            <NewsPanel news={news} onRun={runNews} running={runningNews} />
            <CalendarCard events={calendar} />
          </div>
        )}

        {view === "screener" && (
          <div className="stretch h-full min-h-0">
            <ScreenerPanel onPick={pickAndShow} />
          </div>
        )}

        {view === "heatmap" && (
          <div className="stretch h-full min-h-0">
            <HeatmapPanel onPick={pickAndShow} />
          </div>
        )}

        {view === "risk" && (
          <div className="stretch h-full min-h-0">
            <RiskPanel />
          </div>
        )}

        {view === "calc" && (
          <div className="stretch h-full min-h-0">
            <PositionCalculator
            instrument={instrument}
            defaultEntry={analysis?.indicators.close ?? null}
          />
          </div>
        )}

        {view === "capital" && (
          <div className="stretch grid h-full min-h-0 grid-cols-1 gap-3 lg:grid-cols-2">
            <InvestPanel
                                stats={stats}
                                equity={settings?.account_equity ?? 10000}
                                onEquityChange={async (v) => {
                                  setSettings(await api.saveSettings({ account_equity: v }));
                                  await refreshSignals();
                                }}
                              />
            <UsageCard usage={usage} />
          </div>
        )}

        {view === "trades" && (
          <div className="stretch h-full min-h-0">
            <HistoryTable
                            signals={signals}
                            stats={stats}
                            onEvaluate={evaluate}
                            evaluating={evaluating}
                            onChanged={refreshSignals}
                          />
          </div>
        )}

        {view === "journal" && (
          <div className="stretch h-full min-h-0">
            <JournalPanel signals={signals} aiEnabled={aiEnabled} onChanged={refreshSignals} />
          </div>
        )}

        {view === "backtest" && (
          <div className="stretch h-full min-h-0">
            <BacktestPanel instrument={instrument} watchlist={watchlist} aiEnabled={aiEnabled} />
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default function Page() {
  return (
    <AuthGate>
      {(user, logout) => <Dashboard user={user} logout={logout} />}
    </AuthGate>
  );
}
