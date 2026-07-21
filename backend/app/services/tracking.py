"""Signal persistence, outcome tracking and smart position management.

Every pass re-simulates each open signal from its creation bar — the walk is
deterministic, so trailing stops / break-even / partial take-profits need no
incremental state and always converge to the same outcome.

Bar order inside one candle is conservative: the *current* effective stop is
checked before TP and before any same-bar stop improvements.

Money P&L is exact by construction of the position size (EUR): a stop hit at
the initial SL loses risk_amount, a TP hit gains risk_amount * RR; partial
closes and trailed stops scale linearly in R-space.
"""

from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..indicators import core as ind
from ..models import Signal
from .candles import get_candles, pip_size, price_precision
from .memory import record_trade_close
from .runtime import get_app_config, get_credentials
from .settings import get_settings
from .telegram import format_outcome, send_message

EXPIRY_BARS = 96


def create_signal(db: Session, analysis: dict[str, Any]) -> Signal:
    sig = Signal(
        instrument=analysis["instrument"],
        timeframe=analysis["timeframe"],
        direction=analysis["direction"],
        entry=analysis["levels"]["entry"],
        stop_loss=analysis["levels"]["stop_loss"],
        take_profit=analysis["levels"]["take_profit"],
        risk_reward=analysis["risk_reward"],
        units=analysis["risk"]["units"],
        risk_amount=analysis["risk"]["risk_amount"],
        score=analysis["score"],
        confidence=analysis["confidence"],
        components=analysis["components"],
        status="open",
        strategy=analysis.get("strategy", ""),
        current_sl=analysis["levels"]["stop_loss"],
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return sig


def _walk(sig: Signal, candles: list[dict], settings: dict[str, Any]) -> dict[str, Any]:
    """Replays management rules over completed bars after signal creation.
    Returns the current management state and, if closed, the outcome."""
    created_ts = sig.created_at.replace(tzinfo=timezone.utc).timestamp() \
        if sig.created_at.tzinfo is None else sig.created_at.timestamp()

    high = np.array([c["high"] for c in candles], dtype=np.float64)
    low = np.array([c["low"] for c in candles], dtype=np.float64)
    close = np.array([c["close"] for c in candles], dtype=np.float64)
    atr = ind.atr(high, low, close, 14)

    idx_after = [i for i, c in enumerate(candles)
                 if c["time"] > created_ts and c["complete"]]
    is_buy = sig.direction == "BUY"
    side = 1.0 if is_buy else -1.0
    risk_dist = abs(sig.entry - sig.stop_loss)
    prec = price_precision(sig.instrument)

    eff_sl = sig.stop_loss
    be_moved = False
    partial_taken = False
    partial_r = 0.0

    trailing = bool(settings.get("trailing_enabled"))
    trail_mult = float(settings.get("trailing_atr_mult", 1.5))
    be_at_r = float(settings.get("breakeven_at_r", 0.0))
    partial_on = bool(settings.get("partial_tp_enabled"))
    partial_at_r = float(settings.get("partial_tp_at_r", 1.0))
    partial_frac = min(max(float(settings.get("partial_tp_fraction", 0.5)), 0.05), 0.95)

    def r_of(price: float) -> float:
        return side * (price - sig.entry) / risk_dist if risk_dist > 0 else 0.0

    for n, i in enumerate(idx_after):
        c = candles[i]
        best_r = r_of(c["high"] if is_buy else c["low"])
        # 1) current effective stop first (conservative). A weekend/news gap
        #    can open beyond the stop — then the honest exit is the open, not
        #    the stop price itself.
        hit_sl = c["low"] <= eff_sl if is_buy else c["high"] >= eff_sl
        if hit_sl:
            exit_px = min(eff_sl, c["open"]) if is_buy else max(eff_sl, c["open"])
            return {"closed": True, "status": "hit_sl", "exit": exit_px,
                    "eff_sl": eff_sl, "be_moved": be_moved,
                    "partial_taken": partial_taken, "partial_r": partial_r,
                    "partial_frac": partial_frac}
        # 2) partial fill BEFORE the take-profit check: if one bar reaches both
        #    levels, assuming the (nearer) partial filled first is conservative
        if partial_on and not partial_taken and best_r >= partial_at_r \
                and partial_at_r < float(sig.risk_reward or 0):
            partial_taken = True
            partial_r = partial_at_r
        # 3) take profit (a gap through TP fills at the better open price)
        hit_tp = c["high"] >= sig.take_profit if is_buy else c["low"] <= sig.take_profit
        if hit_tp:
            exit_px = max(sig.take_profit, c["open"]) if is_buy \
                else min(sig.take_profit, c["open"])
            return {"closed": True, "status": "hit_tp", "exit": exit_px,
                    "eff_sl": eff_sl, "be_moved": be_moved,
                    "partial_taken": partial_taken, "partial_r": partial_r,
                    "partial_frac": partial_frac}
        # 4) same-bar stop improvements apply from the NEXT bar's checks
        if be_at_r > 0 and not be_moved and best_r >= be_at_r:
            be_moved = True
            eff_sl = max(eff_sl, sig.entry) if is_buy else min(eff_sl, sig.entry)
        if trailing and not (isinstance(atr[i], float) and np.isnan(atr[i])):
            trail = (c["high"] - trail_mult * float(atr[i]) if is_buy
                     else c["low"] + trail_mult * float(atr[i]))
            eff_sl = max(eff_sl, round(trail, prec)) if is_buy \
                else min(eff_sl, round(trail, prec))
        # 5) expiry
        if n + 1 >= EXPIRY_BARS:
            return {"closed": True, "status": "expired", "exit": c["close"],
                    "eff_sl": eff_sl, "be_moved": be_moved,
                    "partial_taken": partial_taken, "partial_r": partial_r,
                    "partial_frac": partial_frac}

    return {"closed": False, "eff_sl": eff_sl, "be_moved": be_moved,
            "partial_taken": partial_taken, "partial_r": partial_r,
            "partial_frac": partial_frac}


def _apply_outcome(sig: Signal, result: dict[str, Any]) -> None:
    pip = pip_size(sig.instrument)
    risk_dist = abs(sig.entry - sig.stop_loss)
    sl_pips = risk_dist / pip if pip > 0 else 0.0
    side = 1.0 if sig.direction == "BUY" else -1.0
    exit_r = side * (result["exit"] - sig.entry) / risk_dist if risk_dist > 0 else 0.0

    frac = result["partial_frac"] if result["partial_taken"] else 0.0
    partial_money = frac * result["partial_r"] * (sig.risk_amount or 0.0)
    remaining_money = (1.0 - frac) * exit_r * (sig.risk_amount or 0.0)

    sig.status = result["status"]
    sig.pnl_pips = round(exit_r * sl_pips, 1)
    sig.partial_taken = 1 if result["partial_taken"] else 0
    sig.partial_pnl = round(partial_money, 2)
    sig.pnl_money = round(partial_money + remaining_money, 2)
    sig.be_moved = 1 if result["be_moved"] else 0
    sig.current_sl = result["eff_sl"]
    sig.resolved_at = datetime.now(timezone.utc)


def _needed_bars(sig: Signal) -> int:
    """Window must reach back to the signal's creation bar — otherwise early
    SL/TP hits (e.g. while the server was down) would be silently missed."""
    from ..config import TIMEFRAMES

    gran = TIMEFRAMES.get(sig.timeframe, 3600)
    created_ts = sig.created_at.replace(tzinfo=timezone.utc).timestamp() \
        if sig.created_at.tzinfo is None else sig.created_at.timestamp()
    bars_since = int((datetime.now(timezone.utc).timestamp() - created_ts) / gran) + 10
    return min(1500, max(EXPIRY_BARS + 40, bars_since))


async def evaluate_open_signals(db: Session) -> int:
    """Returns number of signals resolved in this pass. Sends Telegram
    notifications for resolved signals when enabled."""
    creds = get_credentials(db)
    settings = get_settings(db)
    open_signals = db.scalars(select(Signal).where(Signal.status == "open")).all()
    resolved: list[Signal] = []
    for sig in open_signals:
        try:
            candles = await get_candles(creds, sig.instrument, sig.timeframe,
                                        _needed_bars(sig))
        except Exception:
            continue
        result = _walk(sig, candles, settings)
        if result["closed"]:
            _apply_outcome(sig, result)
            resolved.append(sig)
        else:
            sig.current_sl = result["eff_sl"]
            sig.be_moved = 1 if result["be_moved"] else 0
            if result["partial_taken"] and not sig.partial_taken:
                sig.partial_taken = 1
                sig.partial_pnl = round(
                    result["partial_frac"] * result["partial_r"] * (sig.risk_amount or 0.0), 2
                )
    db.commit()

    for sig in resolved:
        try:
            record_trade_close(db, sig)
        except Exception:
            pass  # memory must never break tracking

    app_cfg = get_app_config(db)
    if resolved and app_cfg["telegram_enabled"]:
        token = creds["telegram_bot_token"]
        for sig in resolved:
            await send_message(token, app_cfg["telegram_chat_id"], format_outcome(sig))
    return len(resolved)


def signal_stats(db: Session, equity: float) -> dict[str, Any]:
    signals = db.scalars(select(Signal).order_by(Signal.created_at)).all()
    closed = [s for s in signals if s.status in ("hit_tp", "hit_sl", "expired")]
    wins = [s for s in closed if (s.pnl_money or 0) > 0]
    total_pips = sum(s.pnl_pips or 0 for s in closed)
    total_money = sum(s.pnl_money or 0 for s in closed)

    by_tf: dict[str, dict[str, Any]] = {}
    for s in closed:
        b = by_tf.setdefault(s.timeframe, {"count": 0, "wins": 0, "pips": 0.0, "money": 0.0})
        b["count"] += 1
        b["wins"] += 1 if (s.pnl_money or 0) > 0 else 0
        b["pips"] = round(b["pips"] + (s.pnl_pips or 0), 1)
        b["money"] = round(b["money"] + (s.pnl_money or 0), 2)

    # equity curve: starting capital + cumulative realized P&L, by close time
    curve = []
    running = equity
    for s in sorted(closed, key=lambda x: x.resolved_at or x.created_at):
        running += s.pnl_money or 0
        ts = (s.resolved_at or s.created_at)
        curve.append({"time": int(ts.replace(tzinfo=timezone.utc).timestamp()
                                  if ts.tzinfo is None else ts.timestamp()),
                      "value": round(running, 2)})

    open_risk = sum(s.risk_amount or 0 for s in signals if s.status == "open")
    open_potential = sum((s.risk_amount or 0) * s.risk_reward for s in signals if s.status == "open")

    return {
        "total": len(signals),
        "open": sum(1 for s in signals if s.status == "open"),
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(closed) - len(wins),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "total_pips": round(total_pips, 1),
        "total_money": round(total_money, 2),
        "return_pct": round(total_money / equity * 100, 2) if equity else 0.0,
        "current_equity": round(equity + total_money, 2),
        "open_risk": round(open_risk, 2),
        "open_potential": round(open_potential, 2),
        "equity_curve": curve,
        "by_timeframe": by_tf,
    }
