const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  complete: boolean;
}

export interface Overlays {
  ema20: (number | null)[];
  ema50: (number | null)[];
  bb_upper: (number | null)[];
  bb_mid: (number | null)[];
  bb_lower: (number | null)[];
  vwap: (number | null)[];
  rsi: (number | null)[];
  macd: (number | null)[];
  macd_signal: (number | null)[];
  macd_hist: (number | null)[];
  stoch_k: (number | null)[];
  stoch_d: (number | null)[];
  atr: (number | null)[];
  ichimoku_tenkan: (number | null)[];
  ichimoku_kijun: (number | null)[];
  ichimoku_span_a: (number | null)[];
  ichimoku_span_b: (number | null)[];
}

export interface Analysis {
  instrument: string;
  timeframe: string;
  direction: "BUY" | "SELL" | "HOLD";
  score: number;
  confidence: number;
  regime: "trending" | "ranging";
  mode: "conservative" | "aggressive";
  below_threshold: boolean;
  live: {
    score: number;
    direction: "BUY" | "SELL";
    price: number;
    regime: "trending" | "ranging";
  };
  components: Record<string, number>;
  weights: Record<string, number>;
  indicators: Record<string, number | null>;
  levels: {
    entry: number;
    stop_loss: number;
    take_profit: number;
    sl_distance: number;
    tp_distance: number;
  };
  risk: {
    approved: boolean;
    reasons: string[];
    risk_amount: number;
    potential_profit: number;
    units: number;
    notional_eur: number;
    margin_eur: number;
    sl_pips: number;
    tp_pips: number;
    sizing_used: string;
    equity_used: number;
    risk_multiplier: number;
    mode: "conservative" | "aggressive";
    kelly_win_rate: number | null;
    limits: { warnings: string[]; daily_pnl: number; open_risk_pct: number };
  };
  risk_reward: number;
  htf?: { timeframe: string | null; trend: number | null };
  ai: {
    news_pair_sentiment: number;
    prediction: { bias: number; confidence: number; rationale: string };
    analysis_time: string | null;
  };
  last_candle_time: number | null;
  overlays: Overlays;
  candles: Candle[];
}

export interface SignalRow {
  id: number;
  instrument: string;
  timeframe: string;
  direction: string;
  entry: number;
  stop_loss: number;
  take_profit: number;
  risk_reward: number;
  units: number;
  risk_amount: number;
  score: number;
  confidence: number;
  status: string;
  pnl_pips: number | null;
  pnl_money: number | null;
  created_at: string;
  resolved_at: string | null;
  strategy?: string;
  notes?: string;
  current_sl?: number | null;
  be_moved?: number;
  partial_taken?: number;
  partial_pnl?: number;
}

export interface SignalStats {
  total: number;
  open: number;
  closed: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  total_pips: number;
  total_money: number;
  return_pct: number;
  current_equity: number;
  open_risk: number;
  open_potential: number;
  equity_curve: { time: number; value: number }[];
  by_timeframe: Record<string, { count: number; wins: number; pips: number; money: number }>;
}

export interface NewsResult {
  vector: Record<string, number>;
  rationales: Record<string, string>;
  summary: string;
  bull_case: string;
  bear_case: string;
  headlines: string[];
  pair_biases: Record<string, { bias: number; confidence: number; rationale: string }>;
  created_at: string | null;
  enabled: boolean;
  news_times: string[];
}

export interface Settings {
  account_equity: number;
  risk_per_trade_pct: number;
  risk_reward: number;
  sl_atr_multiple: number;
  min_score: number;
  min_adx: number;
  max_open_per_pair: number;
  cooldown_minutes: number;
  ai_weight: number;
  sizing_mode: "fixed" | "half_kelly";
  signal_mode: "conservative" | "aggressive";
  leverage: number;
  trailing_enabled: boolean;
  trailing_atr_mult: number;
  breakeven_at_r: number;
  partial_tp_enabled: boolean;
  partial_tp_at_r: number;
  partial_tp_fraction: number;
  max_daily_loss: number;
  max_daily_losses: number;
  max_drawdown_pct: number;
  daily_profit_target: number;
  max_weekly_loss: number;
  max_monthly_loss: number;
  max_open_risk_pct: number;
  weekend_guard_min: number;
}

export interface AppConfig {
  twelvedata_api_key: string;
  eodhd_api_key: string;
  data_provider: "auto" | "twelvedata" | "eodhd" | "oanda" | "simulation";
  active_provider: string;
  oanda_api_key: string;
  oanda_account_id: string;
  oanda_env: string;
  anthropic_api_key: string;
  telegram_bot_token: string;
  telegram_chat_id: string;
  telegram_enabled: boolean;
  news_times: string[];
  autoscan_enabled: boolean;
  scan_interval_min: number;
  stream_enabled: boolean;
  memory_enabled: boolean;
  notify_signals_enabled: boolean;
  alert_email: string;
  smtp_host: string;
  smtp_port: string;
  smtp_user: string;
  smtp_password: string;
  smtp_from: string;
  metaapi_token: string;
  mt5_login: string;
  mt5_password: string;
  mt5_server: string;
  mt5_symbol_suffix: string;
  mt5_account_id: string;
  autotrade_enabled: boolean;
  autotrade_min_confidence: number;
  autotrade_max_positions: number;
  autotrade_lots: number;
  autotrade_orders_per_signal: number;
  simulated_data: boolean;
  ai_enabled: boolean;
}

export interface Mt5Status {
  ok: boolean;
  configured: boolean;
  connected: boolean;
  state?: string;
  connection_status?: string;
  login?: string;
  server?: string;
  error?: string;
  hint?: string;
  account?: {
    broker: string;
    currency: string;
    balance: number;
    equity: number;
    margin: number;
    free_margin: number;
    leverage: number;
  };
}

export interface Mt5Position {
  id: string;
  symbol: string;
  type: "BUY" | "SELL";
  volume: number;
  open_price: number;
  current_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  profit: number;
  time: string;
  comment: string;
}

export interface Mt5TradeResult {
  ok: boolean;
  symbol: string;
  lots: number;
  order_id?: string;
  position_id?: string;
  orders_opened?: number;
  orders_requested?: number;
  take_profits?: number[];
  position_ids?: (string | undefined)[];
  partial_error?: string;
}

export interface Health {
  status: string;
  app: string;
  simulated_data: boolean;
  provider: string;
  ai_enabled: boolean;
  telegram_enabled: boolean;
  watchlist: string[];
  timeframes: string[];
  currency: string;
}

export interface MarketState {
  now_utc: string;
  epoch: number;
  is_open: boolean;
  sessions: { name: string; active: boolean; open_utc: string; close_utc: string }[];
}

export interface UsageAgg {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  cost_eur: number;
}

export interface UsageStats {
  today: UsageAgg;
  last_30d: UsageAgg;
  eur_usd: number | null;
  recent: {
    created_at: string;
    model: string;
    purpose: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    cost_eur: number;
  }[];
}

// ---------------------------------------------------------------- new types

export interface Quote {
  price: number;
  ts: number;
  source: "ws" | "rest" | "sim" | "candle";
}

export interface PatternPoint {
  time: number;
  price: number;
}

export interface Pattern {
  type: string;
  name: string;
  direction: "bullish" | "bearish" | "neutral";
  status: "forming" | "confirmed";
  confidence: number;
  points: PatternPoint[];
  level?: number;
  explanation: string;
}

export interface SrZone {
  price: number;
  low: number;
  high: number;
  touches: number;
  kind: "support" | "resistance";
  last_touch: number;
}

export interface Trendline {
  side: "support" | "resistance";
  touches: number;
  points: PatternPoint[];
  slope_per_bar: number;
}

export interface Fibonacci {
  direction: "up" | "down";
  swing_high: PatternPoint;
  swing_low: PatternPoint;
  levels: Record<string, number>;
}

export interface PatternsResult {
  patterns: Pattern[];
  sr_zones: SrZone[];
  trendlines: Trendline[];
  fibonacci: Fibonacci | null;
}

export interface RiskLimitsState {
  daily_pnl: number;
  daily_losses: number;
  weekly_pnl: number;
  monthly_pnl: number;
  drawdown_pct: number;
  open_risk: number;
  open_risk_pct: number;
  open_count: number;
  blocked: string[];
  warnings: string[];
  can_trade: boolean;
}

export interface RiskAlert {
  severity: "info" | "warning" | "critical";
  title: string;
  detail: string;
  action: string;
  instrument: string;
}

export interface RiskMonitor {
  positions: {
    id: number;
    instrument: string;
    direction: string;
    timeframe: string;
    entry: number;
    stop_loss: number;
    take_profit: number;
    risk_amount: number;
    price: number | null;
    floating_eur: number | null;
    r_now: number | null;
    be_moved: boolean;
    partial_taken: boolean;
    sl_pips: number;
  }[];
  alerts: RiskAlert[];
  limits: RiskLimitsState;
  floating_eur: number;
  equity: number;
}

export interface PositionSizeResult {
  ok: boolean;
  error?: string;
  units?: number;
  lots?: number;
  risk_eur?: number;
  max_loss_eur?: number;
  risk_pct?: number;
  margin_eur?: number;
  notional_eur?: number;
  sl_distance?: number;
  sl_pips?: number;
  spread_cost_eur?: number;
  commission_eur?: number;
  take_profit_distance?: number;
  potential_profit_eur?: number;
  warnings?: string[];
}

export interface JournalBucket {
  count: number;
  wins: number;
  money: number;
  win_rate: number | null;
}

export interface JournalStats {
  closed: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  avg_win: number;
  avg_loss: number;
  avg_rr_realized: number | null;
  max_drawdown_pct: number;
  max_win_streak: number;
  max_loss_streak: number;
  avg_duration_hours: number | null;
  best_day: { date: string; money: number } | null;
  worst_day: { date: string; money: number } | null;
  by_strategy: Record<string, JournalBucket>;
  by_instrument: Record<string, JournalBucket>;
  by_session: Record<string, JournalBucket>;
  by_weekday: Record<string, JournalBucket>;
}

export interface JournalReview {
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  summary: string;
}

export interface MemoryItem {
  id: number;
  kind: string;
  instrument: string;
  timeframe: string;
  title: string;
  content: string;
  tags: string[];
  importance: number;
  created_at: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SymbolNewsItem {
  headline: string;
  sentiment: "positive" | "neutral" | "negative";
  impact: number;
  why: string;
}

export interface SymbolNews {
  summary: string;
  overall_sentiment: "positive" | "neutral" | "negative";
  items: SymbolNewsItem[];
  instrument: string;
}

export interface AlertRow {
  id: number;
  instrument: string;
  timeframe: string;
  kind: string;
  params: Record<string, unknown>;
  channels: string[];
  active: boolean;
  cooldown_min: number;
  last_fired_at: string | null;
  note: string;
  created_at: string | null;
}

export interface NotificationRow {
  id: number;
  kind: string;
  title: string;
  body: string;
  instrument: string;
  read: boolean;
  source: string;
  created_at: string | null;
}

export interface ScreenerRow {
  symbol: string;
  name: string;
  category: string;
  price: number;
  chg_24h_pct: number;
  chg_5d_pct: number;
  atr_pct: number;
  rsi14: number | null;
  adx14: number | null;
  trend: number;
  roc10: number | null;
  volume_ratio: number;
  breakout: number;
  efficiency: number;
  momentum_score: number;
}

export interface HeatmapResult {
  categories: {
    key: string;
    label: string;
    items: { symbol: string; name: string; chg_pct: number; atr_pct: number; rsi14: number | null }[];
  }[];
  currency_strength: Record<string, number>;
  matrix: Record<string, Record<string, number>>;
}

export interface BacktestMetrics {
  trades: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  profit_factor: number | null;
  expectancy_eur: number | null;
  expectancy_r: number | null;
  sharpe_per_trade: number | null;
  total_return_pct: number;
  final_equity: number;
  max_drawdown_pct: number;
  avg_bars_held: number | null;
  period: { from: number | null; to: number; bars: number };
}

export interface BacktestTrade {
  entry_time: number;
  exit_time: number;
  direction: string;
  entry: number;
  exit: number;
  sl: number;
  tp: number;
  bars_held: number;
  r: number;
  pnl_eur: number;
  status: string;
  score: number;
  equity_after: number;
}

export interface BacktestResult {
  run_id: number;
  instrument: string;
  timeframe: string;
  metrics: BacktestMetrics;
  trades: BacktestTrade[];
  equity_curve: { time: number; value: number }[];
  walk_forward: {
    folds?: { fold: number; optimized_min_score: number; train_pf: number | null; test: Record<string, number | null> }[];
    oos_trades?: number;
    oos_pnl_eur?: number;
    error?: string;
  };
  elapsed_sec: number;
}

export interface DepthLevel {
  price: number;
  size: number;
}

export interface DepthResult {
  instrument: string;
  name: string;
  timeframe: string;
  mid: number;
  synthetic: boolean;
  spread: {
    price: number;
    pips: number;
    lot_cost_eur: number;
    atr_ratio_pct: number | null;
  };
  book: { bids: DepthLevel[]; asks: DepthLevel[] };
  imbalance: number;
  volume_profile: { price: number; volume: number; buy_frac: number }[];
  large_levels: { price: number; volume: number; buy_frac: number }[];
  sr_prices: number[];
}

export interface BacktestRunSummary {
  run_id: number;
  instrument: string;
  timeframe: string;
  params: Record<string, unknown>;
  metrics: BacktestMetrics;
  created_at: string | null;
  ai_analysis: string;
}

const TOKEN_KEY = "cnx_token";

export const getToken = () =>
  typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function handle401(status: number) {
  if (status === 401 && typeof window !== "undefined") {
    clearToken();
    window.dispatchEvent(new Event("cnx-unauthorized"));
  }
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store", headers: authHeaders() });
  if (!r.ok) {
    handle401(r.status);
    throw new Error(`${r.status} ${await r.text()}`);
  }
  return r.json();
}

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method,
    headers: { "content-type": "application/json", ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    handle401(r.status);
    throw new Error(`${r.status} ${await r.text()}`);
  }
  return r.json();
}

export interface CatalogItem {
  symbol: string;
  name: string;
}

export interface InstrumentsResult {
  categories: { key: string; label: string; instruments: CatalogItem[] }[];
  watchlist: string[];
  groups: {
    volatile: (CatalogItem & { atr_pct: number })[];
    ai_recommended: (CatalogItem & { bias: number; rationale: string })[];
  };
}

export interface CalendarEvent {
  title: string;
  currency: string;
  time: number;
  impact: "high" | "medium" | "low";
  forecast: string;
  previous: string;
  relevant: boolean;
}

export interface AuthUser {
  id: number;
  username: string;
  role: "admin" | "user";
  totp_enabled: boolean;
  created_at: string | null;
}

export interface AuditEntry {
  id: number;
  created_at: string | null;
  username: string;
  action: string;
  detail: string;
  ip: string;
}

export const api = {
  // auth
  login: (username: string, password: string, totp_code?: string) =>
    send<{ token?: string; user?: AuthUser; requires_totp?: boolean }>(
      "/api/auth/login", "POST", { username, password, totp_code }),
  logout: () => send<{ ok: boolean }>("/api/auth/logout", "POST"),
  me: () => get<AuthUser>("/api/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    send<{ ok: boolean }>("/api/auth/change-password", "POST", { current_password, new_password }),
  totpSetup: () => send<{ secret: string; uri: string }>("/api/auth/2fa/setup", "POST"),
  totpEnable: (code: string) => send<{ ok: boolean }>("/api/auth/2fa/enable", "POST", { code }),
  totpDisable: (code: string) => send<{ ok: boolean }>("/api/auth/2fa/disable", "POST", { code }),
  // admin
  users: () => get<AuthUser[]>("/api/admin/users"),
  createUser: (username: string, password: string, role: string) =>
    send<AuthUser>("/api/admin/users", "POST", { username, password, role }),
  deleteUser: (id: number) => send<{ ok: boolean }>(`/api/admin/users/${id}`, "DELETE"),
  auditLog: () => get<AuditEntry[]>("/api/admin/audit"),
  // data
  health: () => get<Health>("/api/health"),
  market: () => get<MarketState>("/api/market"),
  calendar: () => get<{ events: CalendarEvent[]; alerts: CalendarEvent[] }>("/api/calendar"),
  instruments: () => get<InstrumentsResult>("/api/instruments"),
  addCustomInstrument: (symbol: string, category: "stocks" | "crypto") =>
    send<{ symbol: string; name: string; category: string }>(
      "/api/instruments/custom", "POST", { symbol, category }),
  saveWatchlist: (watchlist: string[]) =>
    send<{ watchlist: string[] }>("/api/watchlist", "PUT", { watchlist }),
  analysis: (instrument: string, tf: string) =>
    get<Analysis>(`/api/analysis?instrument=${instrument}&tf=${tf}`),
  signals: () => get<{ signals: SignalRow[]; stats: SignalStats }>("/api/signals"),
  news: () => get<NewsResult>("/api/news"),
  runNews: () => send<NewsResult>("/api/news/run", "POST"),
  settings: () => get<Settings>("/api/settings"),
  saveSettings: (patch: Partial<Settings>) => send<Settings>("/api/settings", "PUT", patch),
  config: () => get<AppConfig>("/api/config"),
  saveConfig: (patch: Partial<AppConfig>) => send<AppConfig>("/api/config", "PUT", patch),
  telegramTest: () => send<{ ok: boolean }>("/api/telegram/test", "POST"),
  mt5Status: () => get<Mt5Status>("/api/mt5/status"),
  mt5Connect: () => send<Mt5Status>("/api/mt5/connect", "POST"),
  mt5Positions: () => get<{ ok: boolean; positions: Mt5Position[] }>("/api/mt5/positions"),
  mt5Trade: (body: {
    instrument: string;
    direction: "BUY" | "SELL";
    lots?: number;
    stop_loss?: number;
    take_profit?: number;
    signal_id?: number;
    orders?: number;
  }) => send<Mt5TradeResult>("/api/mt5/trade", "POST", body),
  mt5Close: (position_id: string) =>
    send<{ ok: boolean }>("/api/mt5/close", "POST", { position_id }),
  usage: () => get<UsageStats>("/api/usage"),
  generateSignal: (instrument: string, timeframe: string) =>
    send<{ created: boolean; signal_id?: number; telegram_sent?: boolean; analysis: Analysis }>(
      "/api/signals", "POST", { instrument, timeframe }),
  evaluate: () =>
    send<{ resolved: number; stats: SignalStats }>("/api/signals/evaluate", "POST"),
  deleteSignal: (id: number) =>
    send<{ ok: boolean; stats: SignalStats }>(`/api/signals/${id}`, "DELETE"),
  clearSignals: (req: {
    ids?: number[];
    older_than_days?: number;
    scope?: "closed" | "all";
    instrument?: string;
  }) => send<{ deleted: number; stats: SignalStats }>("/api/signals/clear", "POST", req),
  // quotes / patterns
  quotes: (symbols: string[]) =>
    get<{ quotes: Record<string, Quote>; provider: string }>(
      `/api/quotes?symbols=${symbols.join(",")}`),
  patterns: (instrument: string, tf: string) =>
    get<PatternsResult>(`/api/patterns?instrument=${instrument}&tf=${tf}`),
  depth: (instrument: string, tf: string) =>
    get<DepthResult>(`/api/depth?instrument=${instrument}&tf=${tf}`),
  // risk
  riskMonitor: () => get<RiskMonitor>("/api/risk/monitor"),
  riskLimits: () => get<RiskLimitsState>("/api/risk/limits"),
  positionSize: (req: {
    instrument: string; entry: number; stop_loss: number;
    balance_eur?: number; risk_pct?: number; leverage?: number;
    commission_eur?: number; spread_pips?: number; risk_reward?: number;
  }) => send<PositionSizeResult>("/api/risk/position-size", "POST", req),
  // journal
  journalStats: () => get<JournalStats>("/api/journal/stats"),
  patchSignal: (id: number, patch: { strategy?: string; notes?: string }) =>
    send<{ ok: boolean }>(`/api/signals/${id}`, "PATCH", patch),
  journalReview: () => send<JournalReview>("/api/journal/review", "POST"),
  // memory
  memory: () => get<{ memories: MemoryItem[]; enabled: boolean }>("/api/memory"),
  addMemory: (title: string, content: string, instrument = "") =>
    send<MemoryItem>("/api/memory", "POST", { title, content, instrument }),
  deleteMemory: (id: number) => send<{ ok: boolean }>(`/api/memory/${id}`, "DELETE"),
  consolidateMemory: () =>
    send<{ created: MemoryItem[] }>("/api/memory/consolidate", "POST"),
  // assistant
  chat: (message: string, history: ChatMessage[], instrument = "", timeframe = "1h") =>
    send<{ reply: string }>("/api/assistant/chat", "POST",
      { message, history, instrument, timeframe }),
  symbolNews: (instrument: string) =>
    send<SymbolNews>("/api/assistant/news", "POST", { instrument }),
  // alerts + notifications
  alerts: () => get<{ alerts: AlertRow[]; kinds: string[] }>("/api/alerts"),
  createAlert: (req: {
    instrument: string; timeframe?: string; kind: string;
    params?: Record<string, unknown>; channels?: string[];
    cooldown_min?: number; note?: string;
  }) => send<AlertRow>("/api/alerts", "POST", req),
  patchAlert: (id: number, patch: Partial<Pick<AlertRow, "active" | "params" | "channels" | "cooldown_min" | "note">>) =>
    send<AlertRow>(`/api/alerts/${id}`, "PATCH", patch),
  deleteAlert: (id: number) => send<{ ok: boolean }>(`/api/alerts/${id}`, "DELETE"),
  notifications: (unread = false) =>
    get<{ notifications: NotificationRow[]; unread: number }>(
      `/api/notifications${unread ? "?unread=true" : ""}`),
  markNotificationsRead: (ids?: number[]) =>
    send<{ marked: number }>("/api/notifications/read", "POST", { ids: ids ?? null }),
  // screener / heatmap
  screener: (category: string, force = false) =>
    get<{ rows: ScreenerRow[]; cached_at: number; category: string }>(
      `/api/screener?category=${category}${force ? "&force=true" : ""}`),
  heatmap: () => get<HeatmapResult>("/api/heatmap"),
  // backtest
  runBacktest: (req: Record<string, unknown>) =>
    send<BacktestResult>("/api/backtest", "POST", req),
  backtestRuns: () => get<{ runs: BacktestRunSummary[] }>("/api/backtest/runs"),
  backtestRun: (id: number) =>
    get<BacktestRunSummary & { trades: BacktestTrade[]; equity_curve: { time: number; value: number }[] }>(
      `/api/backtest/runs/${id}`),
  analyzeBacktest: (run_id: number) =>
    send<{ run_id: number; analysis: string }>("/api/backtest/analyze", "POST", { run_id }),
};

export const pretty = (instrument: string) => instrument.replace("_", "/");

// lightweight-charts renders UTC; shift epochs so the chart shows local time
export const toLocalTime = (utcSeconds: number) =>
  utcSeconds - new Date().getTimezoneOffset() * 60;

// Вся денежная отчётность приложения — в евро.
export const fmtMoney = (v: number) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(v);

export const fmtMoney2 = (v: number) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "EUR", minimumFractionDigits: 2 }).format(v);

export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
