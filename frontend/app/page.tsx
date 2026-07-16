"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

const VIEWS = [
  { key: "overview", label: "Обзор" },
  { key: "multi", label: "Мульти" },
  { key: "analytics", label: "ИИ-аналитика" },
  { key: "depth", label: "Стакан" },
  { key: "risk", label: "Риск" },
  { key: "journal", label: "Журнал" },
  { key: "screener", label: "Скринер" },
  { key: "heatmap", label: "Карта" },
  { key: "backtest", label: "Бэктест" },
];

function Dashboard({ user, logout }: { user: AuthUser; logout: () => void }) {
  const [me, setMe] = useState<AuthUser>(user);
  const [view, setView] = useState("overview");
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
      setLastResult(
        r.created
          ? `Сигнал #${r.signal_id} отслеживается${r.telegram_sent ? " · отправлен в Telegram" : ""}.`
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
    setView("overview");
  };

  const groups = instruments?.groups;
  const aiEnabled = config?.ai_enabled ?? false;
  const liveQuote = instrument ? quotes[instrument] : undefined;

  return (
    <div className="min-h-screen bg-[#f5f5f7]">
      <header className="sticky top-0 z-10 border-b border-black/5 bg-white/70 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="h-2.5 w-2.5 rounded-full bg-[#0a84ff]" />
            <h1 className="text-[15px] font-semibold tracking-tight">Codnixy AI Trade</h1>
            <MarketClock />
          </div>
          <div className="flex items-center gap-2">
            {config?.simulated_data ? (
              <Badge variant="secondary" className="rounded-full text-[10px]">
                Симуляция
              </Badge>
            ) : (
              <Badge variant="secondary" className="rounded-full bg-[#0a84ff]/10 text-[10px] text-[#0a84ff]">
                {config?.active_provider === "twelvedata" ? "Twelve Data" : config?.active_provider}
              </Badge>
            )}
            <Badge
              variant="secondary"
              className={`rounded-full text-[10px] ${
                aiEnabled ? "bg-[#34c759]/10 text-[#34c759]" : ""
              }`}
            >
              {aiEnabled ? "ИИ" : "ИИ выкл."}
            </Badge>
            <NotificationsBell />
            <AlertsDialog watchlist={watchlist} instrument={instrument} />
            <ConnectionsDialog config={config} onSaved={(c) => { setConfig(c); refreshMeta(); }} />
            <SettingsDialog
              settings={settings}
              onSave={async (patch) => {
                setSettings(await api.saveSettings(patch));
                await refreshSignals();
              }}
            />
            {me.role === "admin" && <AdminDialog me={me} />}
            <AccountDialog user={me} onUserChange={setMe} />
            <Button variant="ghost" size="sm" className="rounded-xl text-muted-foreground" onClick={logout}>
              Выйти
            </Button>
          </div>
        </div>
        <div className="mx-auto max-w-[1400px] px-6 pb-2">
          <Tabs value={view} onValueChange={setView}>
            <TabsList className="h-8 rounded-xl">
              {VIEWS.map((v) => (
                <TabsTrigger key={v.key} value={v.key} className="rounded-lg px-3 text-xs">
                  {v.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
      </header>

      {alerts.length > 0 && (
        <div className="border-b border-amber-200 bg-amber-50">
          <div className="mx-auto max-w-[1400px] px-6 py-2 text-sm text-amber-900">
            ⚠️{" "}
            {alerts.map((a) => (
              <span key={`${a.time}-${a.title}`} className="mr-4">
                Через {Math.max(1, Math.round((a.time * 1000 - Date.now()) / 60000))} мин —
                важная новость по <b>{a.currency}</b>: {a.title}
              </span>
            ))}
          </div>
        </div>
      )}

      <main className="mx-auto max-w-[1400px] px-6 py-6">
        <div className="grid grid-cols-[220px_1fr] gap-6">
          <aside className="space-y-4">
            <div>
              <p className="mb-2 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Избранное
              </p>
              {watchlist.length === 0 ? (
                <p className="rounded-xl bg-white/60 p-3 text-xs text-muted-foreground">
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
                          ? "bg-white font-semibold shadow-sm"
                          : "text-muted-foreground hover:bg-white/60"
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
                          ? "bg-white font-semibold shadow-sm"
                          : "text-muted-foreground hover:bg-white/60"
                      }`}
                    >
                      <span>{pretty(v.symbol)}</span>
                      <span className="tabular-nums text-[#ff9f0a]">{v.atr_pct}%</span>
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
                          ? "bg-white font-semibold shadow-sm"
                          : "text-muted-foreground hover:bg-white/60"
                      }`}
                    >
                      <span>{pretty(v.symbol)}</span>
                      <span className={`tabular-nums ${v.bias > 0 ? "text-[#34c759]" : "text-[#ff3b30]"}`}>
                        {v.bias > 0 ? "▲" : "▼"} {Math.abs(v.bias).toFixed(2)}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </aside>

          <div className="space-y-6">
            {view === "overview" && (
              <>
                {instrument ? (
                  <div className="grid grid-cols-[1fr_340px] items-start gap-6">
                    <Card className="rounded-2xl border-black/5 shadow-sm">
                      <CardContent className="pt-4">
                        <div className="mb-3 flex items-center justify-between">
                          <div>
                            <h2 className="text-lg font-semibold tracking-tight">
                              {pretty(instrument)}
                              {liveQuote && (
                                <span className="ml-2 text-sm font-normal tabular-nums text-muted-foreground">
                                  {liveQuote.price}
                                  {liveQuote.source === "ws" && (
                                    <span className="ml-1 text-[9px] text-[#34c759]">● live</span>
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
                          <Tabs value={tf} onValueChange={setTf}>
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
                          <ChartControlsBar toggles={toggles} onChange={setToggles} />
                          <DrawToolbar
                            instrument={instrument}
                            timeframe={tf}
                            mode={drawMode}
                            onMode={setDrawMode}
                            onChanged={() => setDrawVersion((v) => v + 1)}
                          />
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
                          <span className="text-[#0a84ff]">—</span> EMA 20&nbsp;&nbsp;
                          <span className="text-[#ff9f0a]">—</span> EMA 50 · время локальное
                          {analysis && analysis.direction !== "HOLD" && " · пунктир: вход / SL / TP"}
                        </p>
                      </CardContent>
                    </Card>

                    <SignalCard
                      analysis={analysis}
                      onGenerate={generate}
                      generating={generating}
                      lastResult={lastResult}
                    />
                  </div>
                ) : (
                  <Card className="rounded-2xl border-black/5 shadow-sm">
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
                )}

                <div className="grid grid-cols-2 gap-6">
                  <ScoreBreakdown analysis={analysis} />
                  <NewsPanel news={news} onRun={runNews} running={runningNews} />
                </div>

                <div className="grid grid-cols-2 gap-6">
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

                <CalendarCard events={calendar} />

                <HistoryTable
                  signals={signals}
                  stats={stats}
                  onEvaluate={evaluate}
                  evaluating={evaluating}
                />
              </>
            )}

            {view === "multi" && <MultiChartGrid watchlist={watchlist} />}

            {view === "analytics" && (
              <>
                <PatternsPanel instrument={instrument} patterns={patterns} aiEnabled={aiEnabled} />
                <div className="grid grid-cols-2 gap-6">
                  <AssistantChat instrument={instrument} timeframe={tf} aiEnabled={aiEnabled} />
                  <MemoryPanel aiEnabled={aiEnabled} />
                </div>
              </>
            )}

            {view === "depth" && <OrderBookPanel instrument={instrument} tf={tf} />}

            {view === "risk" && (
              <>
                <RiskPanel />
                <PositionCalculator
                  instrument={instrument}
                  defaultEntry={analysis?.indicators.close ?? null}
                />
              </>
            )}

            {view === "journal" && (
              <JournalPanel signals={signals} aiEnabled={aiEnabled} onChanged={refreshSignals} />
            )}

            {view === "screener" && <ScreenerPanel onPick={pickAndShow} />}

            {view === "heatmap" && <HeatmapPanel onPick={pickAndShow} />}

            {view === "backtest" && (
              <BacktestPanel instrument={instrument} watchlist={watchlist} aiEnabled={aiEnabled} />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <AuthGate>
      {(user, logout) => <Dashboard user={user} logout={logout} />}
    </AuthGate>
  );
}
