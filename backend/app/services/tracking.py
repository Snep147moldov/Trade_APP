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

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..catalog import meta as catalog_meta
from ..indicators import core as ind
from ..models import Signal
from .candles import get_candles, is_simulated, pip_size, price_precision
from .market import forex_minutes_to_close
from .memory import record_trade_close
from .runtime import get_app_config, get_credentials
from .settings import get_settings
from .telegram import format_outcome, send_message

EXPIRY_BARS = 96
BUCHAREST_TZ = ZoneInfo("Europe/Bucharest")


def confirmation_required(cfg: dict[str, Any]) -> bool:
    """A trade may only reach the broker after an explicit Telegram «Купить».

    Only meaningful when Telegram is actually wired up — with no channel to ask
    on, a pending signal could never be confirmed and every entry would silently
    stall, so the gate stays off in that case.
    """
    return bool(cfg.get("telegram_enabled")
                and cfg.get("telegram_confirm_required", True))


def may_send_to_broker(sig: Signal) -> bool:
    """Single authority for «is this signal allowed to hit the broker?».
    Anything still pending, declined or timed out must never be executed."""
    return (sig.confirm_state or "not_required") in ("not_required", "accepted")


def create_signal(db: Session, analysis: dict[str, Any],
                  cfg: dict[str, Any] | None = None) -> Signal:
    """cfg is the app config; when the Telegram confirmation gate is on the
    signal is stored as `pending` and stays unexecutable until the user taps
    «Купить» (or the deadline passes and it becomes `unconfirmed`)."""
    confirm_state = "not_required"
    expires_at = None
    if cfg is not None and confirmation_required(cfg):
        confirm_state = "pending"
        timeout_min = max(1, int(cfg.get("telegram_confirm_timeout_min", 30)))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_min)

    sig = Signal(
        confirm_state=confirm_state,
        confirm_expires_at=expires_at,
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
    notifications for resolved signals when enabled.

    MT5 sync (mirror mode OR autotrade): the smart management computed here is
    pushed to the broker too — an improved stop (break-even / trailing)
    modifies the matching MT5 positions, and an app-side expiry closes them.
    Covers both manually mirrored ("Codnixy #id") and autotrade positions
    ("Codnixy auto #id"). SL/TP hits need no mirroring: the broker holds
    those levels itself."""
    import re

    creds = get_credentials(db)
    settings = get_settings(db)
    app_cfg = get_app_config(db)
    open_signals = db.scalars(select(Signal).where(Signal.status == "open")).all()

    from . import mt5 as mt5_svc

    mirror = bool(app_cfg.get("mt5_mirror_enabled")
                  or app_cfg.get("autotrade_enabled")) \
        and mt5_svc.is_configured(creds)
    # позиции нужны НЕ только для зеркалирования: пока сделка жива у брокера,
    # её исход определяет он, даже если зеркало и автотрейд выключены (сделку
    # мог открыть пользователь кнопкой «Купить» в Telegram)
    mt5_pos: list[dict] | None = None
    if open_signals and mt5_svc.is_configured(creds):
        p = await mt5_svc.positions(db)
        mt5_pos = p["positions"] if p.get("ok") else None

    def sig_positions(sig_id: int) -> list[dict]:
        if not mt5_pos:
            return []
        pat = re.compile(rf"#{sig_id}(\D|$)")
        return [p for p in mt5_pos if pat.search(p.get("comment") or "")]

    # выходные: рынок закрыт, новых баров нет. Провайдер в этот момент часто
    # не отдаёт ничего, и get_candles молча падает на симулятор — синтетика
    # (сумма синусов) продолжает «двигаться» и закрывает сигналы по TP/SL,
    # которых на рынке не было: сайт рисовал -146.95€ за день, пока у брокера
    # было +37.85€ и баланс не менялся вовсе. Крипта (24/7) не затрагивается.
    forex_closed = forex_minutes_to_close() is None

    resolved: list[Signal] = []
    for sig in open_signals:
        is_crypto = (catalog_meta(sig.instrument) or {}).get("category") == "crypto"
        if forex_closed and not is_crypto:
            continue
        try:
            candles = await get_candles(creds, sig.instrument, sig.timeframe,
                                        _needed_bars(sig))
        except Exception:
            continue
        # синтетические свечи не являются рынком: по ним нельзя ни закрывать
        # сигнал, ни двигать стоп — иначе в БД попадает выдуманный P&L
        if is_simulated(candles):
            continue
        prev_sl = sig.current_sl if sig.current_sl is not None else sig.stop_loss
        result = _walk(sig, candles, settings)
        # позиция ЖИВА у брокера — значит выход определяет он, а не свечи.
        # Приложение считает по mid-ценам Twelve Data и переносит стоп в
        # безубыток само; брокер держит исходный стоп и часто доходит до
        # цели. Расхождение доходило до смены знака: #216 GBP/JPY — hit_sl в
        # приложении при +8.08 EUR у брокера, причём до стопа цена не дошла.
        # Итог таких сделок проставит mt5_sync, когда позиция реально закроется.
        # истечение — исключение: позицию надо закрыть, иначе она останется у
        # брокера навсегда. Итог всё равно проставит mt5_sync по факту выхода.
        broker_positions = sig_positions(sig.id)
        if result["closed"] and broker_positions and result["status"] != "expired":
            sig.current_sl = result["eff_sl"]
            sig.be_moved = 1 if result["be_moved"] else 0
            db.flush()
            continue
        if result["closed"] and result["status"] == "expired" and broker_positions:
            for p in broker_positions:
                try:
                    await mt5_svc.close_position(db, p["id"])
                except Exception:
                    pass
            db.flush()
            continue  # статус и P&L придут из mt5_sync
        if result["closed"]:
            # сюда попадаем только когда позиций у брокера нет — закрытие
            # с живой позицией обработано выше
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
            if mirror and result["eff_sl"] is not None \
                    and abs(result["eff_sl"] - prev_sl) > pip_size(sig.instrument) * 0.5:
                for p in sig_positions(sig.id):
                    try:
                        await mt5_svc.modify_position(
                            db, p["id"], stop_loss=result["eff_sl"],
                            take_profit=p.get("take_profit"))
                    except Exception:
                        pass
    db.commit()

    for sig in resolved:
        try:
            record_trade_close(db, sig)
        except Exception:
            pass  # memory must never break tracking

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

    # realized P&L by close date: today / last 7 days. Границы дня — по
    # Бухаресту, как и дневной отчёт в 22:00 (scheduler._daily_report_tick):
    # на UTC-границе итог за 31.07 приходил в 00:05 и захватывал чужой день.
    now = datetime.now(timezone.utc)
    local_midnight = now.astimezone(BUCHAREST_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0)
    today_start = local_midnight.astimezone(timezone.utc)
    week_start = today_start - timedelta(days=6)

    def closed_at(s: Signal) -> datetime:
        ts = s.resolved_at or s.created_at
        return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts

    today_closed = [s for s in closed if closed_at(s) >= today_start]
    week_closed = [s for s in closed if closed_at(s) >= week_start]
    today_money = sum(s.pnl_money or 0 for s in today_closed)
    week_money = sum(s.pnl_money or 0 for s in week_closed)

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

    # реальные деньги брокера (кэш mt5_sync, обновляется раз в минуту)
    from .mt5_sync import get_state
    mt5_state = get_state(db)
    mt5_total = sum(s.mt5_pnl for s in signals if s.mt5_pnl is not None)

    return {
        "total": len(signals),
        "open": sum(1 for s in signals if s.status == "open"),
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(closed) - len(wins),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "total_pips": round(total_pips, 1),
        "total_money": round(total_money, 2),
        "today_money": round(today_money, 2),
        "today_closed": len(today_closed),
        "today_wins": sum(1 for s in today_closed if (s.pnl_money or 0) > 0),
        "week_money": round(week_money, 2),
        "week_closed": len(week_closed),
        "return_pct": round(total_money / equity * 100, 2) if equity else 0.0,
        "current_equity": round(equity + total_money, 2),
        "open_risk": round(open_risk, 2),
        "open_potential": round(open_potential, 2),
        "equity_curve": curve,
        "by_timeframe": by_tf,
        "mt5": {
            "connected": bool(mt5_state.get("connected")),
            "balance": mt5_state.get("balance"),
            "equity": mt5_state.get("equity"),
            "floating": mt5_state.get("floating"),
            "open_positions": mt5_state.get("open_positions", 0),
            "today_real": mt5_state.get("today_real"),
            "week_real": mt5_state.get("week_real"),
            "signals_total": round(mt5_total, 2),
            "updated_at": mt5_state.get("updated_at"),
        },
    }
