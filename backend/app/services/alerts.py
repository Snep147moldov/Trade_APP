"""Пользовательские алерты: цена, %-движение, RSI, MACD/MA-кроссы, Боллинджер,
волатильность, объём, ИИ-сигналы. Проверяются раз в минуту в фоне.

Каждый вид алерта — детерминированная функция от свежих свечей/индикаторов.
Срабатывание уважает cooldown и доставляется через notify.deliver.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import meta
from ..indicators import core as ind
from ..models import Alert
from .candles import get_candles
from .notify import deliver
from .runtime import get_credentials

KINDS = (
    "price_above", "price_below", "pct_move", "rsi_above", "rsi_below",
    "macd_cross", "ma_cross", "bb_breakout", "atr_spike", "volume_spike",
    "ai_signal",
)


def alert_to_dict(a: Alert) -> dict[str, Any]:
    return {
        "id": a.id, "instrument": a.instrument, "timeframe": a.timeframe,
        "kind": a.kind, "params": a.params, "channels": a.channels,
        "active": bool(a.active), "cooldown_min": a.cooldown_min,
        "last_fired_at": a.last_fired_at.isoformat() if a.last_fired_at else None,
        "note": a.note,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _num(params: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default


def _check(kind: str, params: dict, candles: list[dict]) -> tuple[bool, str]:
    """Returns (fired, human message). Pure function of the candle window."""
    close = np.array([c["close"] for c in candles], dtype=np.float64)
    high = np.array([c["high"] for c in candles], dtype=np.float64)
    low = np.array([c["low"] for c in candles], dtype=np.float64)
    vol = np.array([c["volume"] for c in candles], dtype=np.float64)
    price = float(close[-1])

    if kind == "price_above":
        lvl = _num(params, "level")
        return price > lvl, f"цена {price:.6g} выше уровня {lvl:.6g}"
    if kind == "price_below":
        lvl = _num(params, "level")
        return price < lvl, f"цена {price:.6g} ниже уровня {lvl:.6g}"
    if kind == "pct_move":
        pct = _num(params, "pct", 1.0)
        bars = int(_num(params, "bars", 12)) or 12
        if len(close) <= bars:
            return False, ""
        move = (price / float(close[-1 - bars]) - 1) * 100
        return abs(move) >= pct, f"движение {move:+.2f}% за {bars} баров (порог {pct}%)"
    if kind in ("rsi_above", "rsi_below"):
        lvl = _num(params, "level", 70 if kind == "rsi_above" else 30)
        r = ind.rsi(close, 14)[-1]
        if np.isnan(r):
            return False, ""
        fired = r > lvl if kind == "rsi_above" else r < lvl
        return fired, f"RSI14 = {r:.1f} ({'выше' if kind == 'rsi_above' else 'ниже'} {lvl:.0f})"
    if kind == "macd_cross":
        want = params.get("direction", "bull")  # bull | bear
        line, sig, _ = ind.macd(close)
        if np.isnan(line[-1]) or np.isnan(sig[-1]) or np.isnan(line[-2]) or np.isnan(sig[-2]):
            return False, ""
        crossed_up = line[-2] <= sig[-2] and line[-1] > sig[-1]
        crossed_dn = line[-2] >= sig[-2] and line[-1] < sig[-1]
        if want == "bull" and crossed_up:
            return True, "MACD пересёк сигнальную линию снизу вверх (бычий кросс)"
        if want == "bear" and crossed_dn:
            return True, "MACD пересёк сигнальную линию сверху вниз (медвежий кросс)"
        return False, ""
    if kind == "ma_cross":
        fast_p = int(_num(params, "fast", 20)) or 20
        slow_p = int(_num(params, "slow", 50)) or 50
        want = params.get("direction", "bull")
        fast = ind.ema(close, fast_p)
        slow = ind.ema(close, slow_p)
        if np.isnan(fast[-2]) or np.isnan(slow[-2]):
            return False, ""
        up = fast[-2] <= slow[-2] and fast[-1] > slow[-1]
        dn = fast[-2] >= slow[-2] and fast[-1] < slow[-1]
        if want == "bull" and up:
            return True, f"EMA{fast_p} пересекла EMA{slow_p} вверх (golden cross)"
        if want == "bear" and dn:
            return True, f"EMA{fast_p} пересекла EMA{slow_p} вниз (death cross)"
        return False, ""
    if kind == "bb_breakout":
        _, upper, lower, _ = ind.bollinger(close)
        if np.isnan(upper[-1]):
            return False, ""
        if price > upper[-1]:
            return True, f"закрытие {price:.6g} выше верхней полосы Боллинджера {upper[-1]:.6g}"
        if price < lower[-1]:
            return True, f"закрытие {price:.6g} ниже нижней полосы Боллинджера {lower[-1]:.6g}"
        return False, ""
    if kind == "atr_spike":
        mult = _num(params, "mult", 1.8)
        atr = ind.atr(high, low, close, 14)
        valid = atr[~np.isnan(atr)]
        if len(valid) < 30:
            return False, ""
        avg = float(valid[-30:-1].mean())
        cur = float(valid[-1])
        return cur >= mult * avg, (
            f"ATR14 {cur:.6g} в {cur / avg:.1f}× выше среднего — всплеск волатильности")
    if kind == "volume_spike":
        mult = _num(params, "mult", 2.5)
        if len(vol) < 25 or vol[-21:-1].mean() <= 0:
            return False, ""
        ratio = float(vol[-1]) / float(vol[-21:-1].mean())
        return ratio >= mult, f"объём в {ratio:.1f}× выше среднего за 20 баров"
    return False, ""


async def _check_ai_signal(db: Session, alert: Alert) -> tuple[bool, str]:
    from .analysis import analyze

    min_score = _num(alert.params, "min_score", 0.3)
    result = await analyze(alert.instrument, alert.timeframe, db)
    score = result["score"]
    if abs(score) >= min_score and result["direction"] != "HOLD":
        return True, (f"сигнал {result['direction']} c оценкой {score:+.2f} "
                      f"(порог {min_score})")
    return False, ""


async def evaluate_alerts(db: Session) -> int:
    """One pass over active alerts; returns how many fired."""
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(Alert).where(Alert.active == 1)).all()
    if not rows:
        return 0
    creds = get_credentials(db)
    fired_count = 0

    for a in rows:
        if a.last_fired_at:
            last = a.last_fired_at if a.last_fired_at.tzinfo else \
                a.last_fired_at.replace(tzinfo=timezone.utc)
            if now - last < timedelta(minutes=max(a.cooldown_min, 1)):
                continue
        try:
            if a.kind == "ai_signal":
                fired, msg = await _check_ai_signal(db, a)
            else:
                candles = await get_candles(creds, a.instrument, a.timeframe, 120)
                fired, msg = _check(a.kind, a.params or {}, candles)
        except Exception:
            continue
        if not fired:
            continue
        a.last_fired_at = now
        db.commit()
        fired_count += 1
        name = meta(a.instrument)["name"] if meta(a.instrument) else a.instrument
        title = f"Алерт: {a.instrument.replace('_', '/')} ({a.timeframe})"
        body = f"{name}: {msg}." + (f" Заметка: {a.note}" if a.note else "")
        await deliver(db, title, body, a.channels or ["app"],
                      kind=a.kind, instrument=a.instrument, source="alert")
    return fired_count
