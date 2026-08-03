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
    "min_score": 0.35,             # порог |оценки|: по статистике 66 сделок
                                   # WR растёт с 31% (0.3) до 39% (0.4)
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
    # перенос SL в безубыток при +N R (0 = выкл). Было 1.0: на живой истории
    # 36 сделок из 199 (18%) доходили до +1R, ловили перенесённый стоп и
    # закрывались ровно в 0.00 EUR. При цели 1.8R перенос на 1.0R слишком
    # ранний — 1.3R оставляет ходу до цели.
    "breakeven_at_r": 1.3,
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
    # за сколько минут до закрытия рынка (пятница 21:00 UTC) блокировать
    # новые сигналы: гэп через выходные может перескочить стоп-лосс.
    # 0 = выключено. Крипта (24/7) не затрагивается.
    "weekend_guard_min": 90.0,
    # час (по Бухаресту, 0-23), после которого новые сделки не открываются —
    # торговый день завершён; открытые позиции не трогает. 0 = выключено.
    "daily_cutoff_hour": 22,
    # час (Бухарест), когда сигналы снова разрешены после ночной паузы.
    # 9:00 — открытие Лондона: до него ликвидность тонкая, спред шире, и стоп
    # срывает движением, которого днём бы не было (16 ночных сигналов подряд
    # закрылись по стопу). Между cutoff и этим часом сигналы НЕ создаются.
    "quiet_resume_hour": 9,
    # какую долю расстояния до стопа может занимать спред «туда-обратно».
    # 0.25 = расходы не больше четверти риска. Отсекает альткоины, где спред
    # 0.5–2% цены против стопа 1.5*ATR: замеры показывают падение winrate
    # с ~30% до 12% (спред 1%) и до 5% (спред 2%). 0 = выключить проверку.
    "max_cost_ratio": 0.25,
    # во сколько раз реальная позиция может превысить задуманный риск, когда
    # минимальный лот брокера крупнее нужного. 1.25 = терпим 25% сверху.
    # Металлы при малом депозите не проходят: XAU 4h с риском 8 EUR требует
    # 0.29 унции, а минимум брокера — 1 унция (риск x3.5). Поднять это значение
    # = сознательно рисковать больше расчётного; 99 = снять проверку совсем.
    "max_risk_overshoot": 1.25,
    # до какого превышения риска сделку ещё можно открыть ВРУЧНУЮ — с явным
    # вторым подтверждением в Telegram («да, только по этой сделке рискую
    # больше»). Между max_risk_overshoot и этим порогом сигнал доходит с
    # кнопкой и предупреждением; выше — кнопки нет вовсе.
    # 3.0 при депозите 438 EUR и риске 1.37 EUR = максимум ~4.10 EUR (<1%).
    "max_manual_overshoot": 3.0,
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
    # уведомления, когда движок уверен по инструменту из «Избранного»
    "notify_signals_enabled": True,
    # сканировать и рынки ВНЕ избранного (форекс/металлы/индексы/крипто) и
    # пушить, когда движок уверен, что можно входить
    "notify_all_markets": True,
    # минимальная уверенность (%) для сигналов ВНЕ «Избранного»: каталог
    # брокера — сотни инструментов, и без порога скан присылает десятки
    # уведомлений в день по парам, которые пользователь не выбирал.
    # Порог режет ШУМ, но не повышает качество: связь уверенности с исходом
    # на этих данных не установлена. Просадка сегмента >80% (-106.82 EUR на
    # 7 сделках) объяснялась не уверенностью, а тем, что при высокой
    # уверенности открывалось 3 ордера, каждый — полного размера (см.
    # signal_lots, исправлено).
    "market_scan_min_confidence": 70,
    # --- автоторговля через MT5 (MetaApi). Выключена по умолчанию: включая,
    # пользователь явно берёт ответственность на себя. Робот открывает позицию
    # только по сигналу автосканера, прошедшему риск-менеджер, при уверенности
    # не ниже порога; SL/TP ставятся сразу в ордере (выход ведёт брокер).
    # Подтверждение сделки в Telegram. Пока включено, НИ автоскан, ни
    # зеркалирование не отправляют ордер сами: сигнал ждёт кнопки «Купить».
    # «Пропустить» или отсутствие ответа за telegram_confirm_timeout_min
    # означают, что сделка НЕ открывается.
    "telegram_confirm_required": True,
    "telegram_confirm_timeout_min": 30,
    "autotrade_enabled": False,
    "autotrade_min_confidence": 75,   # %, минимальная уверенность движка
    "autotrade_max_positions": 2,     # макс. одновременных позиций в MT5
    "autotrade_lots": 0.01,           # объём одной сделки, лоты
    # сколько ордеров можно открыть по ОДНОМУ сигналу, когда движок очень
    # уверен: 1 на пороге, +1 за каждые 8 п.п. уверенности сверх порога.
    # Тейк-профиты ставятся ступенями (+1R, цель, цель*1.5) — общий SL один.
    "autotrade_orders_per_signal": 1,
    # зеркалирование в MT5: каждый созданный вручную сигнал открывает сделку,
    # безубыток/трейлинг двигают SL у брокера, истечение закрывает позицию
    "mt5_mirror_enabled": False,
    # объём как на сайте: лот считается из риск-менеджера (units сигнала /
    # размер контракта), а не фиксированный autotrade_lots. Ограничен
    # autotrade_max_lots — защита от неверного размера контракта у брокера.
    "autotrade_risk_sizing": False,
    "autotrade_max_lots": 0.5,
}
