"""Daily / weekly / monthly risk limits (all EUR) and portfolio-level state.

Deterministic bookkeeping over the signals table. When a configured limit is
breached, `blocked` carries explicit reasons — the signal gate refuses new
trades until the period rolls over or the user lifts the limit.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Signal

CLOSED = ("hit_tp", "hit_sl", "expired")


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def day_state(db: Session, settings: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())
    month_start = day_start.replace(day=1)

    signals = db.scalars(select(Signal)).all()
    closed = [s for s in signals if s.status in CLOSED and s.resolved_at]
    open_sigs = [s for s in signals if s.status == "open"]

    def pnl_since(start: datetime) -> float:
        return sum((s.pnl_money or 0.0) for s in closed if _utc(s.resolved_at) >= start)

    daily_pnl = pnl_since(day_start)
    weekly_pnl = pnl_since(week_start)
    monthly_pnl = pnl_since(month_start)
    daily_losses = sum(
        1 for s in closed
        if _utc(s.resolved_at) >= day_start and (s.pnl_money or 0.0) < 0
    )

    # drawdown from the running equity peak (whole history)
    equity = settings["account_equity"]
    peak = equity
    running = equity
    for s in sorted(closed, key=lambda x: _utc(x.resolved_at)):
        running += s.pnl_money or 0.0
        peak = max(peak, running)
    drawdown_pct = (peak - running) / peak * 100.0 if peak > 0 else 0.0

    open_risk = sum(s.risk_amount or 0.0 for s in open_sigs)
    open_risk_pct = open_risk / equity * 100.0 if equity > 0 else 0.0

    blocked: list[str] = []
    warnings: list[str] = []

    def gate(limit: float, value: float, blocked_msg: str, warn_msg: str,
             warn_ratio: float = 0.8) -> None:
        if limit <= 0:
            return
        if value >= limit:
            blocked.append(blocked_msg)
        elif value >= limit * warn_ratio:
            warnings.append(warn_msg)

    gate(settings["max_daily_loss"], -daily_pnl,
         f"дневной лимит убытка достигнут ({-daily_pnl:.0f}€ из {settings['max_daily_loss']:.0f}€)",
         f"близко к дневному лимиту убытка ({-daily_pnl:.0f}€ из {settings['max_daily_loss']:.0f}€)")
    gate(float(settings["max_daily_losses"]), float(daily_losses),
         f"{daily_losses} убыточных сделок сегодня (лимит {settings['max_daily_losses']})",
         f"{daily_losses} убыточных сделок сегодня (лимит {settings['max_daily_losses']})")
    gate(settings["max_weekly_loss"], -weekly_pnl,
         f"недельный лимит убытка достигнут ({-weekly_pnl:.0f}€)",
         f"близко к недельному лимиту убытка ({-weekly_pnl:.0f}€)")
    gate(settings["max_monthly_loss"], -monthly_pnl,
         f"месячный лимит убытка достигнут ({-monthly_pnl:.0f}€)",
         f"близко к месячному лимиту убытка ({-monthly_pnl:.0f}€)")
    gate(settings["max_drawdown_pct"], drawdown_pct,
         f"максимальная просадка достигнута ({drawdown_pct:.1f}%)",
         f"просадка {drawdown_pct:.1f}% приближается к лимиту {settings['max_drawdown_pct']:.0f}%")

    if settings["daily_profit_target"] > 0 and daily_pnl >= settings["daily_profit_target"]:
        blocked.append(
            f"дневная цель прибыли достигнута (+{daily_pnl:.0f}€) — торговля остановлена"
        )

    if settings["max_open_risk_pct"] > 0 and open_risk_pct >= settings["max_open_risk_pct"]:
        blocked.append(
            f"суммарный открытый риск {open_risk_pct:.1f}% ≥ лимита "
            f"{settings['max_open_risk_pct']:.0f}%"
        )

    return {
        "daily_pnl": round(daily_pnl, 2),
        "daily_losses": daily_losses,
        "weekly_pnl": round(weekly_pnl, 2),
        "monthly_pnl": round(monthly_pnl, 2),
        "drawdown_pct": round(drawdown_pct, 2),
        "open_risk": round(open_risk, 2),
        "open_risk_pct": round(open_risk_pct, 2),
        "open_count": len(open_sigs),
        "blocked": blocked,
        "warnings": warnings,
        "can_trade": not blocked,
    }
