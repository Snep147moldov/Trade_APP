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
from ..performance import closed_sample, net_pnl, wilson_interval
from . import memory
from .runtime import log_usage
from ..i18n import answer_language_clause, t

CLOSED = ("hit_tp", "hit_sl", "expired")

WEEKDAYS = [t("Пн"), t("Вт"), t("Ср"), t("Чт"), t("Пт"), t("Сб"), t("Вс")]


def session_of(dt) -> str:
    h = dt.astimezone(timezone.utc).hour if dt.tzinfo else dt.hour
    if 7 <= h < 12:
        return t("Лондон")
    if 12 <= h < 16:
        return t("Лондон+НЙ")
    if 16 <= h < 21:
        return t("Нью-Йорк")
    return t("Азия")


def _bucket() -> dict[str, Any]:
    return {"count": 0, "wins": 0, "money": 0.0}


def _add(b: dict[str, Any], s: Signal) -> None:
    b["count"] += 1
    b["wins"] += 1 if (net_pnl(s) or 0) > 0 else 0
    b["money"] = round(b["money"] + (net_pnl(s) or 0), 2)


def _finish(groups: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    for b in groups.values():
        b["win_rate"] = round(b["wins"] / b["count"] * 100, 1) if b["count"] else None
    return dict(sorted(groups.items(), key=lambda kv: -kv[1]["money"]))


def journal_stats(db: Session, equity: float) -> dict[str, Any]:
    signals = db.scalars(select(Signal).order_by(Signal.created_at)).all()
    closed, source = closed_sample(list(signals))

    wins = [s for s in closed if (net_pnl(s) or 0) > 0]
    losses = [s for s in closed if (net_pnl(s) or 0) < 0]
    gross_win = sum(net_pnl(s) or 0 for s in wins)
    gross_loss = -sum(net_pnl(s) or 0 for s in losses)

    # streaks + drawdown + daily P&L
    max_win_streak = max_loss_streak = cur_win = cur_loss = 0
    running = equity
    peak = equity
    max_dd = 0.0
    daily: dict[str, float] = defaultdict(float)
    durations: list[float] = []

    for s in sorted(closed, key=lambda x: x.resolved_at or x.created_at):
        pnl = net_pnl(s) or 0
        if pnl > 0:
            cur_win += 1
            cur_loss = 0
        elif pnl < 0:
            cur_loss += 1
            cur_win = 0
        else:
            cur_win = cur_loss = 0
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
        _add(by_strategy[s.strategy or t("без стратегии")], s)
        _add(by_instrument[s.instrument], s)
        _add(by_session[session_of(s.created_at)], s)
        _add(by_weekday[WEEKDAYS[s.created_at.weekday()]], s)

    best_day = max(daily.items(), key=lambda kv: kv[1], default=None)
    worst_day = min(daily.items(), key=lambda kv: kv[1], default=None)

    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0

    return {
        "closed": len(closed),
        "source": source,
        "excluded_closed": sum(s.status in CLOSED for s in signals) - len(closed),
        "breakevens": len(closed) - len(wins) - len(losses),
        "win_rate_ci95": wilson_interval(len(wins), len(closed)),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "expectancy": round(sum(net_pnl(s) or 0 for s in closed) / len(closed), 2)
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
        strengths: list[str] = Field(description=t("сильные стороны, по-русски"))
        weaknesses: list[str] = Field(description=t("слабые места и повторяющиеся ошибки"))
        suggestions: list[str] = Field(description=t("конкретные улучшения, максимум 5"))
        summary: str = Field(description=t("итог в 2 предложениях"))

    stats = journal_stats(db, equity)
    recent = db.scalars(select(Signal).where(Signal.status.in_(CLOSED))
                        .order_by(Signal.resolved_at.desc()).limit(25)).all()
    trades_txt = "\n".join(
        f"- {s.instrument} {s.timeframe} {s.direction} → {s.status} "
        f"{(net_pnl(s) or 0):+.2f}€ (score {s.score:+.2f}"
        + (t(", стратегия {0}", f"{s.strategy}") if s.strategy else "")
        + (t(", заметка: {0}", f"{s.notes[:120]}") if s.notes else "") + ")"
        for s in recent
    )
    mem_ctx = memory.context_block(db)

    client = AsyncAnthropic(api_key=anthropic_key)
    try:
        resp = await client.messages.parse(
            model=SONNET_MODEL,
            max_tokens=1500,
            system=t("Ты — трейдинг-коуч. Проанализируй журнал сделок: найди сильные стороны, повторяющиеся ошибки и дай конкретные улучшения. Опирайся только на данные. По-русски, без воды.") + answer_language_clause(),
            messages=[{"role": "user", "content":
                       t("Статистика журнала:\n{0}\n\nПоследние сделки:\n{1}\n\nНакопленная память:\n{2}", f"{stats}", f"{trades_txt or '—'}", f"{mem_ctx}")}],
            output_format=Review,
        )
        log_usage(SONNET_MODEL, "journal_review",
                  resp.usage.input_tokens, resp.usage.output_tokens)
        parsed = resp.parsed_output
    finally:
        await client.close()

    if not parsed:
        return {"summary": t("Не удалось получить разбор."), "strengths": [],
                "weaknesses": [], "suggestions": []}

    memory.add_memory(
        db, "journal_insight", t("Разбор журнала"),
        parsed.summary + t(" Советы: ") + "; ".join(parsed.suggestions[:3]),
        importance=0.7, tags=["journal"])

    return parsed.model_dump()
