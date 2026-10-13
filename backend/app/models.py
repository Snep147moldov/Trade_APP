from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    direction: Mapped[str] = mapped_column(String(4))  # BUY | SELL
    entry: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float] = mapped_column(Float)
    risk_reward: Mapped[float] = mapped_column(Float)
    units: Mapped[float] = mapped_column(Float)  # suggested position size
    risk_amount: Mapped[float] = mapped_column(Float, default=0.0)  # EUR at risk
    score: Mapped[float] = mapped_column(Float)  # confluence score [-1, 1]
    confidence: Mapped[float] = mapped_column(Float)  # 0..1
    components: Mapped[dict] = mapped_column(JSON)  # per-factor score breakdown
    # open | hit_tp | hit_sl | expired
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)
    pnl_pips: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_money: Mapped[float | None] = mapped_column(Float, nullable=True)  # EUR
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # --- journal & smart-management fields ---
    strategy: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    ai_review: Mapped[str] = mapped_column(Text, default="")
    current_sl: Mapped[float | None] = mapped_column(Float, nullable=True)  # trailing
    be_moved: Mapped[int] = mapped_column(Integer, default=0)       # SL -> entry done
    partial_taken: Mapped[int] = mapped_column(Integer, default=0)  # partial TP done
    partial_pnl: Mapped[float] = mapped_column(Float, default=0.0)  # realized EUR
    # --- Telegram confirmation gate ---
    # not_required | pending | accepted | declined | unconfirmed (timed out).
    # Nothing may reach the broker while this is anything other than
    # "not_required" or "accepted".
    confirm_state: Mapped[str] = mapped_column(
        String(12), default="not_required", index=True
    )
    confirm_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # --- real broker outcome (MT5 via MetaApi), synced by services/mt5_sync ---
    mt5_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)  # EUR, closed deals
    mt5_volume: Mapped[float] = mapped_column(Float, default=0.0)   # total lots opened
    mt5_orders: Mapped[int] = mapped_column(Integer, default=0)     # orders opened


class NewsAnalysis(Base):
    """One row per scheduled AI run (Haiku triage -> Sonnet debate -> pair bias)."""

    __tablename__ = "news_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    vector: Mapped[dict] = mapped_column(JSON)        # {"USD": 0.1, ...}
    rationales: Mapped[dict] = mapped_column(JSON)    # {"USD": "...", ...}
    summary: Mapped[str] = mapped_column(String(2000), default="")
    bull_case: Mapped[str] = mapped_column(String(2000), default="")
    bear_case: Mapped[str] = mapped_column(String(2000), default="")
    headlines: Mapped[list] = mapped_column(JSON, default=list)
    pair_biases: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"EUR_USD": {"bias": 0.2, "confidence": 0.6, "rationale": "..."}}
    news_items: Mapped[list] = mapped_column(JSON, default=list)
    # ranked per-headline intel: [{"headline", "sentiment", "impact",
    #                              "why", "currencies": [..]}]


class ApiUsage(Base):
    """Every Anthropic call: tokens + estimated cost, shown in the UI."""

    __tablename__ = "api_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    model: Mapped[str] = mapped_column(String(48))
    purpose: Mapped[str] = mapped_column(String(48))  # triage | debate | pair_bias | ...
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class BrokerDeal(Base):
    """Idempotent broker ledger; deal tickets are unique within an account."""

    __tablename__ = "broker_deals"
    account_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    deal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(12), default="user")  # admin | user
    # адрес для восстановления доступа. Пустой = восстановление недоступно:
    # общий ящик из настроек для этого не годится — по нему любой пользователь
    # смог бы сбросить чужой пароль, включая админский
    email: Mapped[str] = mapped_column(String(160), default="")
    # язык интерфейса и уведомлений. Хранится на пользователе, а не в
    # настройках приложения: Telegram и почта уходят конкретному человеку,
    # а настройки общие на установку
    language: Mapped[str] = mapped_column(String(5), default="ru")
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[int] = mapped_column(Integer, default=0)  # 0/1
    # одноразовый код сброса: хранится хешем, как и пароль
    reset_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reset_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    token: Mapped[str] = mapped_column(String(96), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(48), index=True)
    detail: Mapped[str] = mapped_column(String(512), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")


class AiMemory(Base):
    """Persistent AI knowledge: lessons from closed trades, factor statistics,
    regime observations, user style, journal insights. Retrieved into every
    AI prompt so the assistant keeps learning between sessions."""

    __tablename__ = "ai_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # lesson | trade_review | pattern_stat | regime | user_style | journal_insight
    kind: Mapped[str] = mapped_column(String(24), index=True)
    instrument: Mapped[str] = mapped_column(String(16), default="", index=True)
    timeframe: Mapped[str] = mapped_column(String(8), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    importance: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    archived: Mapped[int] = mapped_column(Integer, default=0, index=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    instrument: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), default="1h")
    # price_above | price_below | pct_move | rsi_above | rsi_below | macd_cross
    # ma_cross | bb_breakout | atr_spike | volume_spike | ai_signal
    kind: Mapped[str] = mapped_column(String(24))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    channels: Mapped[list] = mapped_column(JSON, default=list)  # app|telegram|email
    active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    cooldown_min: Mapped[int] = mapped_column(Integer, default=60)
    last_fired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str] = mapped_column(String(200), default="")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    kind: Mapped[str] = mapped_column(String(24), default="alert")
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(String(2000), default="")
    instrument: Mapped[str] = mapped_column(String(16), default="")
    read: Mapped[int] = mapped_column(Integer, default=0, index=True)
    source: Mapped[str] = mapped_column(String(16), default="alert")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    instrument: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    equity_curve: Mapped[list] = mapped_column(JSON, default=list)
    trades: Mapped[list] = mapped_column(JSON, default=list)
    walk_forward: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_analysis: Mapped[str] = mapped_column(Text, default="")



# --------------------------------------------------------------------------
# Подписки и оплаты
#
# Тарифы — строки в таблице, а не перечисление в коде: добавить тариф или
# поменять его лимиты нужно уметь без выката. Права (`entitlements`) тоже
# данные: один словарь, который читает единственная проверка на сервере.
# --------------------------------------------------------------------------


class Plan(Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(256), default="")
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    # длительность периода в днях (30 — месяц, 365 — год)
    period_days: Mapped[int] = mapped_column(Integer, default=30)
    # что тариф разрешает; ключи — ENTITLEMENT_KEYS из billing/plans.py
    entitlements: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[int] = mapped_column(Integer, default=1)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Subscription(Base):
    """Подписка пользователя. Одна активная на пользователя.

    `status` — единственный источник правды о доступе. Ни один экран не
    сравнивает даты сам: иначе две проверки разойдутся, и человек увидит
    «активна» на одной странице и «истекла» на другой.
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    plan_code: Mapped[str] = mapped_column(String(32), index=True)
    # trialing | active | past_due | suspended | cancelled | expired
    status: Mapped[str] = mapped_column(String(16), default="trialing", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # конец оплаченного периода: после него начинается отсчёт льготных дней
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # сколько дней после неоплаты доступ ещё работает
    grace_days: Mapped[int] = mapped_column(Integer, default=3)
    # отмена в конце периода: доступ не отбирают посреди оплаченного срока
    cancel_at_period_end: Mapped[int] = mapped_column(Integer, default=0)
    trial: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Payment(Base):
    """Факт оплаты. Пишется и вручную администратором (банковский перевод),
    и платёжным провайдером, поэтому `source` обязателен."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    plan_code: Mapped[str] = mapped_column(String(32), default="")
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    # paid | failed | refunded
    status: Mapped[str] = mapped_column(String(16), default="paid", index=True)
    # manual | stripe | …
    source: Mapped[str] = mapped_column(String(16), default="manual")
    # идентификатор у провайдера; уникален, чтобы вебхук не провёл платёж дважды
    external_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    invoice_no: Mapped[str] = mapped_column(String(32), default="")
    note: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class BillingNotice(Base):
    """Отправленное предупреждение об оплате.

    Существует ради одной гарантии: одно окно — одно уведомление. Планировщик
    и вход в приложение считают «пора предупредить» независимо, и без этой
    записи человек получал бы два письма подряд.
    """

    __tablename__ = "billing_notices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    # d7 | d3 | d1 | due | past_due | suspended
    kind: Mapped[str] = mapped_column(String(16), index=True)
    # окно, к которому относится предупреждение: конец периода в ISO-дате.
    # Вместе с kind даёт ключ идемпотентности
    window_key: Mapped[str] = mapped_column(String(32), index=True)
    channel: Mapped[str] = mapped_column(String(16), default="app")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class UserEvent(Base):
    """Что делал пользователь: вход, сигнал, сделка, смена настроек.

    Отдельно от `audit_log`: тот пишет действия над системой (кто создал
    пользователя, кто сменил настройку), а этот — активность самого человека,
    которую админ смотрит по каждому аккаунту.
    """

    __tablename__ = "user_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[str] = mapped_column(String(512), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class ContentOverride(Base):
    """Текст витрины, переписанный из админки.

    Ключ — исходная английская строка сайта, та же, что служит ключом его
    словаря переводов. Так редактируемым становится весь текст, который уже
    обёрнут в `t()`, без переразметки сайта: админка меняет перевод, а не
    выдумывает новое поле.

    Отсутствие строки здесь означает «как в коде» — удалить правку и вернуть
    исходный текст можно, не зная, что там было.
    """

    __tablename__ = "content_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # исходная строка (английская) — ключ словаря сайта
    source: Mapped[str] = mapped_column(Text, index=True)
    # en | ru | fr | de
    locale: Mapped[str] = mapped_column(String(5), index=True)
    value: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class CustomerProfile(Base):
    """То, что администратор помнит о клиенте помимо его подписки.

    Метки, заметка и «следующий шаг» — поля, которых нет в платёжных данных,
    но без которых список клиентов остаётся просто выгрузкой таблицы.
    Заведено по образцу CRM-карточек: ручной следующий шаг старше любого
    вычисленного, потому что человек знает про клиента то, чего нет в базе.
    """

    __tablename__ = "customer_profiles"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(String(256), default="")
    next_action_due: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # поднимается наверх в каждом списке, пока снова не снимут
    urgent: Mapped[int] = mapped_column(Integer, default=0)
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
