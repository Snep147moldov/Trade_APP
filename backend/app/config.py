import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

APP_NAME = "Codnixy AI Trade"

# Env values act as fallbacks; keys entered in the app UI (stored in DB)
# take priority. See services/runtime.py.
ENV_TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()
ENV_EODHD_API_KEY = os.getenv("EODHD_API_KEY", "").strip()
ENV_OANDA_API_KEY = os.getenv("OANDA_API_KEY", "").strip()
ENV_OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "").strip()
ENV_OANDA_ENV = os.getenv("OANDA_ENV", "practice").strip()
ENV_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ENV_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./forex.db")

OANDA_HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}

TWELVEDATA_HOST = "https://api.twelvedata.com"
TWELVEDATA_WS = "wss://ws.twelvedata.com/v1/quotes/price"

SONNET_MODEL = "claude-sonnet-5"
HAIKU_MODEL = "claude-haiku-4-5"

# USD per MTok — Sonnet 5 intro pricing valid through 2026-08-31, then 3/15.
MODEL_PRICES = {
    SONNET_MODEL: {"input": 2.0, "output": 10.0},
    HAIKU_MODEL: {"input": 1.0, "output": 5.0},
}

G8 = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"]

# Приложение считает всё в евро.
ACCOUNT_CURRENCY = "EUR"

# Supported timeframes, in seconds. 40m has no native granularity anywhere —
# resampled from 5m. 1m requires a paid Twelve Data plan (Grow+); on free
# keys it silently degrades to the simulator like everything else.
TIMEFRAMES = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "40m": 40 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
}

# Strategy settings (persisted in DB, editable in the UI). Money values — EUR.
DEFAULT_SETTINGS = {
    "account_equity": 10000.0,     # инвестируемая сумма, EUR
    "risk_per_trade_pct": 1.0,     # % капитала на сделку (режим fixed)
    "risk_reward": 1.8,            # TP = risk_reward * дистанция SL
    "sl_atr_multiple": 1.5,        # SL = sl_atr_multiple * ATR(14)
    "min_score": 0.30,             # порог |совокупной оценки| для сигнала
    "min_adx": 18.0,               # ниже — флэтовый режим
    "max_open_per_pair": 1,        # открытых сигналов на пару
    "cooldown_minutes": 30,        # пауза между сигналами, пара+ТФ
    "ai_weight": 0.15,             # доля ИИ в формуле (0 = только формулы)
    "sizing_mode": "fixed",        # fixed | half_kelly (Kelly 1956, Thorp)
    # conservative: сигнал только при |оценке| >= min_score (ОЖИДАНИЕ иначе)
    # aggressive:   всегда ПОКУПКА/ПРОДАЖА по знаку оценки; ниже порога —
    #               половинный размер позиции. Автоскан остаётся консервативным.
    "signal_mode": "conservative",
    "leverage": 30.0,              # плечо для расчёта маржи
    # --- умные SL/TP ---
    "trailing_enabled": False,     # трейлинг-стоп по ATR
    "trailing_atr_mult": 1.5,      # дистанция трейлинга = mult * ATR14
    "breakeven_at_r": 1.0,         # перенос SL в безубыток при +N R (0 = выкл)
    "partial_tp_enabled": False,   # частичная фиксация
    "partial_tp_at_r": 1.0,        # уровень частичной фиксации, R
    "partial_tp_fraction": 0.5,    # доля позиции при частичной фиксации
    # --- дневные/периодные лимиты риска (0 = выключено), EUR ---
    "max_daily_loss": 0.0,         # макс. дневной убыток
    "max_daily_losses": 0,         # макс. убыточных сделок в день
    "max_drawdown_pct": 0.0,       # макс. просадка от пика капитала, %
    "daily_profit_target": 0.0,    # дневная цель прибыли (стоп после)
    "max_weekly_loss": 0.0,        # недельный лимит убытка
    "max_monthly_loss": 0.0,       # месячный лимит убытка
    "max_open_risk_pct": 5.0,      # суммарный открытый риск, % капитала
}

# App-level configuration (watchlist, schedule, telegram) — persisted in DB.
DEFAULT_APP_CONFIG = {
    "watchlist": [],                     # пусто — пользователь выбирает сам
    "news_times": ["07:00", "13:30"],    # UTC, запуски ИИ-анализа
    "autoscan_enabled": False,
    "scan_interval_min": 15,
    "telegram_enabled": False,
    "telegram_chat_id": "",
    # simulation | twelvedata | eodhd | oanda | auto
    # (auto: twelvedata -> eodhd -> oanda -> sim, per symbol and timeframe)
    "data_provider": "auto",
    "alert_email": "",                   # адрес для e-mail уведомлений
    "stream_enabled": True,              # WebSocket-поток цен Twelve Data
    "memory_enabled": True,              # ИИ-память: уроки и разборы сделок
}
