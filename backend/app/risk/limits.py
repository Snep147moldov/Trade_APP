"""Daily / weekly / monthly risk limits (all EUR) and portfolio-level state.

Deterministic bookkeeping over the signals table. When a configured limit is
breached, `blocked` carries explicit reasons — the signal gate refuses new
trades until the period rolls over or the user lifts the limit.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import G8
from ..models import Signal
from ..performance import closed_sample, net_pnl
from ..i18n import t

CLOSED = ("hit_tp", "hit_sl", "expired")


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def current_equity(db: Session, settings: dict[str, Any]) -> float:
    """Капитал для расчёта риска: РЕАЛЬНЫЙ баланс брокера, когда MT5 подключён.

    Иначе — стартовый капитал плюс собственный реализованный P&L (режим без
    брокера, где все сигналы всё равно бумажные).

    Складывать pnl_money закрытых сигналов с балансом брокера нельзя: баланс
    уже включает реализованные деньги, а большинство сигналов в базе к брокеру
    вообще не уходили (unconfirmed / declined, orders=0).
    """
    try:
        from ..services.mt5_sync import get_state

        st = get_state(db)
        if st.get("connected") and st.get("balance") is not None:
            return max(float(st["balance"]), 0.0)
    except Exception:
        pass
    from ..services.runtime import get_credentials
    from ..services.mt5 import is_configured
    if is_configured(get_credentials(db)):
        # A connected account's failed balance refresh must never create an
        # imaginary paper bankroll for the next live order.
        return 0.0
    realized = 0.0
    signals = list(db.scalars(select(Signal)).all())
    closed, source = closed_sample(signals)
    realized = sum(net_pnl(s) or 0.0 for s in closed)
    for s in signals:
        if source == "paper" and s.status == "open" and s.partial_taken:
            realized += s.partial_pnl or 0.0
    return max(settings["account_equity"] + realized, 0.0)


# сигнал ещё может дойти до брокера только в этих состояниях; unconfirmed и
# declined не несут никакого реального риска, сколько бы их ни висело открытыми
_EXECUTABLE_STATES = ("not_required", "accepted", "pending")


def currency_exposure(signals: list[Signal]) -> dict[tuple[str, int], float]:
    """Риск по каждой валюте и стороне: {(валюта, +1/-1): сумма риска, EUR}.

    Покупка EUR/USD — это одновременно ставка ЗА евро и ПРОТИВ доллара. Поэтому
    EUR/USD BUY, GBP/USD BUY, NZD/USD BUY и USD/CAD SELL — не четыре сделки, а
    одна ставка на падение доллара, взятая четыре раза. 19 августа так и вышло:
    пять одновременных позиций, все против доллара, все закрылись в 17:17
    вместе. День дал +89 EUR — но тем же механизмом даёт -89, когда ставка
    неверна (17 августа: связка по йене, почти вся в минусе).
    """
    out: dict[tuple[str, int], float] = {}
    for s in signals:
        parts = s.instrument.split("_")
        if len(parts) != 2:
            continue
        base, quote = parts
        side = 1 if s.direction == "BUY" else -1
        risk = s.risk_amount or 0.0
        for ccy, sign in ((base, side), (quote, -side)):
            if ccy in G8:
                out[(ccy, sign)] = out.get((ccy, sign), 0.0) + risk
    return out


def day_state(db: Session, settings: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())
    month_start = day_start.replace(day=1)

    signals = db.scalars(select(Signal)).all()
    sample, _ = closed_sample(list(signals))
    closed = [s for s in sample if s.resolved_at]
    open_sigs = [s for s in signals if s.status == "open"]

    def pnl_since(start: datetime) -> float:
        return sum((net_pnl(s) or 0.0) for s in closed if _utc(s.resolved_at) >= start)

    daily_pnl = pnl_since(day_start)
    weekly_pnl = pnl_since(week_start)
    monthly_pnl = pnl_since(month_start)
    daily_losses = sum(
        1 for s in closed
        if _utc(s.resolved_at) >= day_start and (net_pnl(s) or 0.0) < 0
    )

    # drawdown from the running equity peak (whole history)
    start_equity = settings["account_equity"]
    peak = start_equity
    running = start_equity
    for s in sorted(closed, key=lambda x: _utc(x.resolved_at)):
        running += net_pnl(s) or 0.0
        peak = max(peak, running)
    drawdown_pct = (peak - running) / peak * 100.0 if peak > 0 else 0.0

    # открытый риск = РЕАЛЬНАЯ экспозиция на рынке, то есть сигналы, по которым
    # у брокера действительно стоят ордера. Сигнал без ордеров не рискует
    # ничем, сколько бы ни висел открытым.
    #
    # Фильтра по confirm_state недостаточно: 30 августа шесть сигналов на 1d в
    # состоянии not_required (то есть РАЗРЕШЁННЫХ) висели с суммарным «риском»
    # 75.64 EUR при капитале 98.19 — 77% против лимита 12%. Ни один к брокеру
    # не уходил. Они блокировали и новые сигналы, и самих себя, а при
    # expiry_bars=96 на дневном таймфрейме простояли бы так 96 дней.
    equity = current_equity(db, settings)
    live = [s for s in open_sigs if (s.mt5_orders or 0) > 0]
    open_risk = sum(s.risk_amount or 0.0 for s in live)
    open_risk_pct = open_risk / equity * 100.0 if equity > 0 else 0.0
    exposure = currency_exposure(live)

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
         t("дневной лимит убытка достигнут ({0}€ из {1}€)", f"{-daily_pnl:.0f}", f"{settings['max_daily_loss']:.0f}"),
         t("близко к дневному лимиту убытка ({0}€ из {1}€)", f"{-daily_pnl:.0f}", f"{settings['max_daily_loss']:.0f}"))
    gate(float(settings["max_daily_losses"]), float(daily_losses),
         t("{0} убыточных сделок сегодня (лимит {1})", f"{daily_losses}", f"{settings['max_daily_losses']}"),
         t("{0} убыточных сделок сегодня (лимит {1})", f"{daily_losses}", f"{settings['max_daily_losses']}"))
    gate(settings["max_weekly_loss"], -weekly_pnl,
         t("недельный лимит убытка достигнут ({0}€)", f"{-weekly_pnl:.0f}"),
         t("близко к недельному лимиту убытка ({0}€)", f"{-weekly_pnl:.0f}"))
    gate(settings["max_monthly_loss"], -monthly_pnl,
         t("месячный лимит убытка достигнут ({0}€)", f"{-monthly_pnl:.0f}"),
         t("близко к месячному лимиту убытка ({0}€)", f"{-monthly_pnl:.0f}"))
    gate(settings["max_drawdown_pct"], drawdown_pct,
         t("максимальная просадка достигнута ({0}%)", f"{drawdown_pct:.1f}"),
         t("просадка {0}% приближается к лимиту {1}%", f"{drawdown_pct:.1f}", f"{settings['max_drawdown_pct']:.0f}"))

    if settings["daily_profit_target"] > 0 and daily_pnl >= settings["daily_profit_target"]:
        blocked.append(
            t("дневная цель прибыли достигнута (+{0}€) — торговля остановлена", f"{daily_pnl:.0f}")
        )

    if settings["max_open_risk_pct"] > 0 and open_risk_pct >= settings["max_open_risk_pct"]:
        blocked.append(
            t("суммарный открытый риск {0}% ≥ лимита {1}%", f"{open_risk_pct:.1f}", f"{settings['max_open_risk_pct']:.0f}")
        )

    return {
        "currency_exposure": {f"{c}{'+' if s > 0 else '-'}": round(v, 2)
                              for (c, s), v in sorted(exposure.items(),
                                                      key=lambda kv: -kv[1])},
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
