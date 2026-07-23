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


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(12), default="user")  # admin | user
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[int] = mapped_column(Integer, default=0)  # 0/1
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
