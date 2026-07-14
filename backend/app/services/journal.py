"""Торговый журнал: расширенная статистика по закрытым сигналам + ИИ-разбор.

Every metric is EUR-denominated and derived on the fly from the signals
table; the AI review is stored both in memory (kind=journal_insight) and
returned to the UI.
"""

from collections import defaultdict
from datetime import timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SONNET_MODEL
from ..models import Signal
from . import memory
from .runtime import log_usage

CLOSED = ("hit_tp", "hit_sl", "expired")

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def session_of(dt) -> str:
    h = dt.astimezone(timezone.utc).hour if dt.tzinfo else dt.hour
    if 7 <= h < 12:
        return "Лондон"
    if 12 <= h < 16:
        return "Лондон+НЙ"
    if 16 <= h < 21:
        return "Нью-Йорк"
    return "Азия"


def _bucket() -> dict[str, Any]:
    return {"count": 0, "wins": 0, "money": 0.0}


def _add(b: dict[str, Any], s: Signal) -> None:
    b["count"] += 1
    b["wins"] += 1 if (s.pnl_money or 0) > 0 else 0
    b["money"] = round(b["money"] + (s.pnl_money or 0), 2)


def _finish(groups: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    for b in groups.values():
        b["win_rate"] = round(b["wins"] / b["count"] * 100, 1) if b["count"] else None
    return dict(sorted(groups.items(), key=lambda kv: -kv[1]["money"]))


def journal_stats(db: Session, equity: float) -> dict[str, Any]:
    signals = db.scalars(select(Signal).order_by(Signal.created_at)).all()
    closed = [s for s in signals if s.status in CLOSED]

    wins = [s for s in closed if (s.pnl_money or 0) > 0]
    losses = [s for s in closed if (s.pnl_money or 0) <= 0]
    gross_win = sum(s.pnl_money or 0 for s in wins)
    gross_loss = -sum(s.pnl_money or 0 for s in losses)

    # streaks + drawdown + daily P&L
    max_win_streak = max_loss_streak = cur_win = cur_loss = 0
    running = equity
    peak = equity
    max_dd = 0.0
    daily: dict[str, float] = defaultdict(float)
    durations: list[float] = []

    for s in sorted(closed, key=lambda x: x.resolved_at or x.created_at):
        pnl = s.pnl_money or 0
        if pnl > 0:
            cur_win += 1
            cur_loss = 0
        else:
            cur_loss += 1
            cur_win = 0
        max_win_streak = max(max_win_streak, cur_win)
        max_loss_streak = max(max_loss_streak, cur_loss)
        running += pnl
        peak = max(peak, running)
        max_dd = max(max_dd, (peak - running) / peak * 100 if peak > 0 else 0)
        ts = s.resolved_at or s.created_at
        daily[ts.strftime("%Y-%m-%d")] += pnl
        if s.resolved_at and s.created_at:
            durations.append((s.resolved_at - s.created_at).total_seconds() / 3600)

    by_strategy: dict[str, dict] = defaultdict(_bucket)
    by_instrument: dict[str, dict] = defaultdict(_bucket)
    by_session: dict[str, dict] = defaultdict(_bucket)
    by_weekday: dict[str, dict] = defaultdict(_bucket)
    for s in closed:
        _add(by_strategy[s.strategy or "без стратегии"], s)
        _add(by_instrument[s.instrument], s)
        _add(by_session[session_of(s.created_at)], s)
        _add(by_weekday[WEEKDAYS[s.created_at.weekday()]], s)

    best_day = max(daily.items(), key=lambda kv: kv[1], default=None)
    worst_day = min(daily.items(), key=lambda kv: kv[1], default=None)

    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0

    return {
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "expectancy": round(sum(s.pnl_money or 0 for s in closed) / len(closed), 2)
        if closed else None,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "avg_rr_realized": round(avg_win / avg_loss, 2) if avg_loss > 0 else None,
        "max_drawdown_pct": round(max_dd, 2),
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "avg_duration_hours": round(sum(durations) / len(durations), 1) if durations else None,
        "best_day": {"date": best_day[0], "money": round(best_day[1], 2)} if best_day else None,
        "worst_day": {"date": worst_day[0], "money": round(worst_day[1], 2)} if worst_day else None,
        "by_strategy": _finish(by_strategy),
        "by_instrument": _finish(by_instrument),
        "by_session": _finish(by_session),
        "by_weekday": _finish(by_weekday),
    }


async def ai_review(db: Session, anthropic_key: str, equity: float) -> dict[str, Any]:
    """Sonnet reads the journal and returns strengths / weaknesses / advice."""
    from anthropic import AsyncAnthropic
    from pydantic import BaseModel, Field

    class Review(BaseModel):
        strengths: list[str] = Field(description="сильные стороны, по-русски")
        weaknesses: list[str] = Field(description="слабые места и повторяющиеся ошибки")
        suggestions: list[str] = Field(description="конкретные улучшения, максимум 5")
        summary: str = Field(description="итог в 2 предложениях")

    stats = journal_stats(db, equity)
    recent = db.scalars(select(Signal).where(Signal.status.in_(CLOSED))
                        .order_by(Signal.resolved_at.desc()).limit(25)).all()
    trades_txt = "\n".join(
        f"- {s.instrument} {s.timeframe} {s.direction} → {s.status} "
        f"{(s.pnl_money or 0):+.2f}€ (score {s.score:+.2f}"
        + (f", стратегия {s.strategy}" if s.strategy else "")
        + (f", заметка: {s.notes[:120]}" if s.notes else "") + ")"
        for s in recent
    )
    mem_ctx = memory.context_block(db)

    client = AsyncAnthropic(api_key=anthropic_key)
    try:
        resp = await client.messages.parse(
            model=SONNET_MODEL,
            max_tokens=1500,
            system="Ты — трейдинг-коуч. Проанализируй журнал сделок: найди сильные "
                   "стороны, повторяющиеся ошибки и дай конкретные улучшения. "
                   "Опирайся только на данные. По-русски, без воды.",
            messages=[{"role": "user", "content":
                       f"Статистика журнала:\n{stats}\n\nПоследние сделки:\n"
                       f"{trades_txt or '—'}\n\nНакопленная память:\n{mem_ctx}"}],
            output_format=Review,
        )
        log_usage(SONNET_MODEL, "journal_review",
                  resp.usage.input_tokens, resp.usage.output_tokens)
        parsed = resp.parsed_output
    finally:
        await client.close()

    if not parsed:
        return {"summary": "Не удалось получить разбор.", "strengths": [],
                "weaknesses": [], "suggestions": []}

    memory.add_memory(
        db, "journal_insight", "Разбор журнала",
        parsed.summary + " Советы: " + "; ".join(parsed.suggestions[:3]),
        importance=0.7, tags=["journal"])

    return parsed.model_dump()
