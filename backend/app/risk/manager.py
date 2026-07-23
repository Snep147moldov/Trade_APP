"""Deterministic risk manager (роль «Risk Management Team» из схемы).

Pure rule gates — no randomness, no AI. A candidate signal must pass every
gate; each rejection carries an explicit reason (in Russian, shown in the UI).
Money is EUR throughout.

Position sizing:
  fixed       units = risk_eur / (stop_distance * eur_per_quote_unit)
  half_kelly  risk fraction = max(0, W - (1-W)/R) / 2  (Kelly 1956; Thorp),
              where W = tracked win rate (needs >= 20 closed signals),
              R = risk:reward. Capped at 5% of equity; falls back to fixed.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import meta as catalog_meta
from ..models import Signal
from ..services.candles import pip_size
from ..services.market import forex_minutes_to_close
from . import limits as risk_limits

KELLY_MIN_TRADES = 20
KELLY_RISK_CAP = 0.05  # never risk more than 5% of equity per trade


def _kelly_fraction(db: Session, risk_reward: float) -> tuple[float | None, float | None]:
    closed = db.scalars(
        select(Signal).where(Signal.status.in_(("hit_tp", "hit_sl", "expired")))
    ).all()
    if len(closed) < KELLY_MIN_TRADES or risk_reward <= 0:
        return None, None
    wins = sum(1 for s in closed if (s.pnl_pips or 0) > 0)
    w = wins / len(closed)
    f = w - (1 - w) / risk_reward
    return max(0.0, f / 2), w


def evaluate(
    db: Session,
    instrument: str,
    timeframe: str,
    direction: str,
    score: float,
    snap: dict[str, Any],
    levels: dict[str, float],
    settings: dict[str, Any],
    eur_per_quote: float = 1.0,
    aggressive: bool = False,
    below_threshold: bool = False,
    htf_score: float | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    pip = pip_size(instrument)

    if direction == "HOLD":
        reasons.append(
            f"совокупная оценка {score:+.2f} ниже порога ±{settings['min_score']}"
        )

    # 1m gate: по собранной статистике (32 сделки, WR 22%) движок на 1m
    # системно убыточен — спред и шум съедают преимущество формулы
    if direction != "HOLD" and timeframe == "1m":
        reasons.append("таймфрейм 1m заблокирован: статистически убыточен "
                       "(спред/шум); используйте 15m и выше")

    # counter-trend guard: сигнал ПРОТИВ выраженного тренда старшего ТФ
    # требует заметно более сильной оценки (статистика: такие входы — WR 16%)
    if direction in ("BUY", "SELL") and htf_score is not None and abs(htf_score) >= 0.5:
        fights_htf = (direction == "BUY" and htf_score < 0) or \
                     (direction == "SELL" and htf_score > 0)
        need = settings["min_score"] * 1.25
        if fights_htf and abs(score) < need:
            reasons.append(
                f"против тренда старшего ТФ ({htf_score:+.2f}) — "
                f"нужна оценка не ниже ±{need:.2f}")

    # ranging-market gate: weak trend demands a stronger score.
    # Aggressive mode accepts these entries knowingly (at reduced size).
    adx = snap.get("adx14")
    hurst = snap.get("hurst", 0.5)
    if (not aggressive and direction != "HOLD" and adx is not None
            and adx < settings["min_adx"] and hurst < 0.55):
        if abs(score) < settings["min_score"] * 1.3:
            reasons.append(
                f"флэт (ADX {adx:.1f} < {settings['min_adx']:.0f}, Hurst {hurst:.2f}) — "
                f"оценка недостаточно сильная"
            )

    sl_pips = levels["sl_distance"] / pip
    if sl_pips < 5:
        reasons.append(f"стоп-лосс {sl_pips:.1f} п. — слишком близко (< 5 п.)")

    if settings["risk_reward"] < 1.0:
        reasons.append("соотношение риск/прибыль ниже 1.0")

    # exposure gate: max open signals per instrument
    open_count = len(
        db.scalars(
            select(Signal.id).where(Signal.instrument == instrument, Signal.status == "open")
        ).all()
    )
    if direction != "HOLD" and open_count >= settings["max_open_per_pair"]:
        reasons.append(
            f"{open_count} открыт(ых) сигнал(ов) по {instrument.replace('_', '/')} "
            f"(макс. {settings['max_open_per_pair']})"
        )

    # circuit breaker: 3 подряд стопа по инструменту -> пауза 24 часа
    # (данные: серия из 6 стопов по NVDA — такие полосы надо прерывать)
    if direction != "HOLD":
        recent_closed = db.scalars(
            select(Signal).where(
                Signal.instrument == instrument,
                Signal.status.in_(("hit_tp", "hit_sl", "expired")),
            ).order_by(Signal.resolved_at.desc()).limit(3)
        ).all()
        if len(recent_closed) == 3 and all(s.status == "hit_sl" for s in recent_closed):
            last_loss = recent_closed[0].resolved_at
            if last_loss is not None:
                last_loss = last_loss.replace(tzinfo=timezone.utc) \
                    if last_loss.tzinfo is None else last_loss
                since_h = (datetime.now(timezone.utc) - last_loss).total_seconds() / 3600
                if since_h < 24:
                    reasons.append(
                        f"3 стопа подряд по {instrument.replace('_', '/')} — "
                        f"пауза 24ч (осталось {24 - since_h:.0f}ч)")

    # cooldown gate: no repeat signal on same pair+tf within window
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings["cooldown_minutes"])
    recent = db.scalars(
        select(Signal.id).where(
            Signal.instrument == instrument,
            Signal.timeframe == timeframe,
            Signal.created_at >= cutoff,
        )
    ).all()
    if direction != "HOLD" and recent:
        reasons.append(
            f"пауза: сигнал по {instrument.replace('_', '/')} {timeframe} "
            f"уже был за последние {settings['cooldown_minutes']} мин"
        )

    # daily / weekly / drawdown / exposure limits (EUR)
    state = risk_limits.day_state(db, settings)
    if direction != "HOLD":
        reasons.extend(state["blocked"])

    # weekend guard: a position opened right before the Friday close can gap
    # straight past its stop-loss on Sunday open. Crypto (24/7) is exempt.
    close_warnings: list[str] = []
    cat = (catalog_meta(instrument) or {}).get("category", "")
    guard = float(settings.get("weekend_guard_min", 90.0))
    if cat != "crypto" and guard > 0:
        mins = forex_minutes_to_close()
        if mins is None:
            if direction != "HOLD":
                reasons.append("рынок закрыт (выходные) — исполнение невозможно до открытия")
        elif mins <= guard:
            if direction != "HOLD":
                reasons.append(
                    f"рынок закрывается через {mins:.0f} мин — вход перед выходными "
                    f"опасен: гэп в воскресенье может перескочить стоп-лосс")
        elif mins <= guard * 3:
            close_warnings.append(
                f"до закрытия рынка {mins:.0f} мин — новые входы скоро будут "
                f"заблокированы; открытые позиции рассмотрите закрыть до пятницы 21:00 UTC")

    # position sizing (EUR) — on CURRENT equity: starting capital + realized
    # P&L (incl. partial closes), matching how the backtest compounds
    realized = 0.0
    for s in db.scalars(select(Signal)).all():
        if s.status in ("hit_tp", "hit_sl", "expired"):
            realized += s.pnl_money or 0.0
        elif s.partial_taken:
            realized += s.partial_pnl or 0.0
    equity = max(settings["account_equity"] + realized, 0.0)
    fixed_fraction = settings["risk_per_trade_pct"] / 100.0
    sizing_mode = settings.get("sizing_mode", "fixed")
    kelly_f, win_rate_used = (None, None)
    if sizing_mode == "half_kelly":
        kelly_f, win_rate_used = _kelly_fraction(db, settings["risk_reward"])

    if kelly_f is not None and kelly_f > 0:
        risk_fraction = min(kelly_f, KELLY_RISK_CAP)
        sizing_used = "half_kelly"
    else:
        risk_fraction = fixed_fraction
        sizing_used = "fixed"

    # aggressive entries below the normal score threshold carry no confirmed
    # statistical edge — they get exactly half the standard position
    risk_multiplier = 0.5 if (aggressive and below_threshold) else 1.0

    # 19:00–23:59 UTC: тонкая ликвидность позднего US + ролловер, спреды
    # расширяются (статистика: 11 сделок, 1 прибыльная) — размер ×0.5
    if 19 <= datetime.now(timezone.utc).hour <= 23:
        risk_multiplier *= 0.5
        close_warnings.append(
            "19–23 UTC: тонкая ликвидность и широкие спреды — "
            "размер позиции уменьшен вдвое")
    risk_amount = equity * risk_fraction * risk_multiplier  # EUR
    denom = levels["sl_distance"] * max(eur_per_quote, 1e-12)
    units = risk_amount / denom if levels["sl_distance"] > 0 else 0.0

    notional_eur = units * levels["entry"] * eur_per_quote
    leverage = max(settings.get("leverage", 30.0), 1.0)
    margin_eur = notional_eur / leverage

    return {
        "approved": direction != "HOLD" and not reasons,
        "reasons": reasons,
        "risk_amount": round(risk_amount, 2),
        "potential_profit": round(risk_amount * settings["risk_reward"], 2),
        "units": round(units),
        "notional_eur": round(notional_eur, 2),
        "margin_eur": round(margin_eur, 2),
        "sl_pips": round(sl_pips, 1),
        "tp_pips": round(levels["tp_distance"] / pip, 1),
        "sizing_used": sizing_used,
        "equity_used": round(equity, 2),
        "risk_multiplier": risk_multiplier,
        "mode": "aggressive" if aggressive else "conservative",
        "kelly_win_rate": round(win_rate_used * 100, 1) if win_rate_used is not None else None,
        "limits": {
            "warnings": state["warnings"] + close_warnings,
            "daily_pnl": state["daily_pnl"],
            "open_risk_pct": state["open_risk_pct"],
        },
    }
